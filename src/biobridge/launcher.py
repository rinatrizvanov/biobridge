"""BioBridge launcher (M0 feasibility spike).

Sets up the SpliceAI engine with the bundled uv, downloads GRCh38 chromosome 17,
runs one real SpliceAI prediction on a synthetic demo variant, and shows it on a
localhost page. Long work runs on a background thread; the window only receives
updates, so it stays responsive. A heartbeat measures how late the UI event loop
runs and logs the worst delay for each stage. Quit stops every child process.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

import toga
from toga.style import Pack

from biobridge import paths
from biobridge.demo_server import ResultServer
from biobridge.setup.envs import InstallError, engine_ready, install_engine, sanitized_env
from biobridge.setup.processes import Cancelled, ChildProcesses, alive
from biobridge.setup.reference import ensure_chromosome

# A synthetic test variant at a real GRCh38 position (BRCA1, chr17). Not a clinical example.
DEMO = {"chrom": "chr17", "pos": 43057051, "ref": "C", "alt": "T", "id": "demo_synthetic_variant"}
LICENSE_NOTICE = (
    "SpliceAI's trained models are licensed CC BY-NC 4.0: academic and non-commercial use only. "
    "Commercial use, including research at companies, requires a license from Illumina."
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {"time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
                 "event": record.getMessage()}
        entry.update(getattr(record, "data", {}))
        return json.dumps(entry)


def make_logger() -> logging.Logger:
    paths.logs().mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("biobridge.launcher")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(paths.logs() / "launcher.log")
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    return logger


# NSActivityUserInitiated: keeps macOS from App-Napping BioBridge (which throttles its
# timers and work while the window is in the background) and from idle-sleeping the
# Mac in the middle of setup.
NS_ACTIVITY_USER_INITIATED = 0x00FFFFFF


def begin_activity(reason: str):
    try:
        from rubicon.objc import ObjCClass

        info = ObjCClass("NSProcessInfo").processInfo
        return info, info.beginActivityWithOptions(NS_ACTIVITY_USER_INITIATED, reason=reason)
    except Exception:  # Never let a missing power assertion stop setup.
        return None


def end_activity(handle) -> None:
    if handle:
        info, token = handle
        info.endActivity(token)


def find_uv() -> Path:
    from uv import find_uv_bin

    return Path(find_uv_bin())


class BioBridge(toga.App):
    def startup(self) -> None:
        self.base = paths.home()
        self.base.mkdir(parents=True, exist_ok=True)
        self.log = make_logger()
        self.procs = ChildProcesses()
        self.server: ResultServer | None = None
        self.worker: threading.Thread | None = None
        self.stage = "idle"
        self.stage_lag = 0.0
        self.started = time.monotonic()
        self.settings_path = self.base / "settings.json"
        self.settings = self._load_settings()

        self.status = toga.Label("Ready.", style=Pack(margin_bottom=4))
        self.detail = toga.Label("", style=Pack(margin_bottom=6, font_size=11))
        self.progress = toga.ProgressBar(max=None, style=Pack(margin_bottom=6))
        self.clock = toga.Label("", style=Pack(font_size=11, margin_bottom=8))
        self.ack = toga.Switch("I will use SpliceAI only for academic or non-commercial research.",
                               value=bool(self.settings.get("engine_license_ack")))
        self.run_button = toga.Button("Set up and run demo", on_press=self.on_run)
        self.open_button = toga.Button("Open result in browser", on_press=self.on_open, enabled=False)
        quit_button = toga.Button("Quit", on_press=lambda w: self.request_exit())

        box = toga.Box(style=Pack(direction="column", margin=16))
        box.add(toga.Label("BioBridge — experimental feasibility build", style=Pack(font_weight="bold", margin_bottom=8)))
        box.add(toga.Label(LICENSE_NOTICE, style=Pack(margin_bottom=8, font_size=11)))
        box.add(self.ack)
        box.add(toga.Box(style=Pack(margin_top=8, margin_bottom=8),
                         children=[self.run_button, self.open_button, quit_button]))
        for widget in (self.status, self.detail, self.progress, self.clock):
            box.add(widget)
        self.main_window = toga.MainWindow(title=self.formal_name, size=(640, 360))
        self.main_window.content = box
        self.main_window.show()
        self.on_exit = self.handle_exit
        # `kill` (SIGTERM) gets the same orderly cleanup as Quit. The heartbeat keeps
        # Python running every 0.1 s, so the handler fires promptly.
        signal.signal(signal.SIGTERM, lambda *_: self.loop.call_soon_threadsafe(self.request_exit))

        self.log.info("launch", extra={"data": {
            "python": sys.executable, "uv": str(find_uv()), "app_path": str(Path(__file__).parent),
            "home": str(self.base), "inherited_PATH": os.environ.get("PATH", ""),
        }})
        self.loop.create_task(self.heartbeat())
        if self.settings.get("engine_license_ack"):
            self.start_pipeline()

    # --- settings ------------------------------------------------------------------
    def _load_settings(self) -> dict:
        try:
            return json.loads(self.settings_path.read_text())
        except (OSError, ValueError):
            return {}

    def _save_settings(self) -> None:
        self.settings_path.write_text(json.dumps(self.settings, indent=1))

    # --- UI helpers (called from any thread) ---------------------------------------
    def ui(self, fn, *args) -> None:
        self.loop.call_soon_threadsafe(fn, *args)

    def set_stage(self, text: str, determinate: bool = False) -> None:
        self.log.info("stage", extra={"data": {"stage": text, "previous": self.stage,
                                               "previous_max_ui_lag_ms": round(self.stage_lag * 1000, 1)}})
        self.stage, self.stage_lag = text, 0.0

        def apply():
            self.status.text = text
            self.detail.text = ""
            self.progress.max = 1.0 if determinate else None
            self.progress.value = 0.0
            self.progress.start()
        self.ui(apply)

    def set_detail(self, text: str) -> None:
        self.ui(setattr, self.detail, "text", text[:110])

    def set_fraction(self, done: int, total: int | None) -> None:
        if total:
            self.ui(setattr, self.progress, "value", min(1.0, done / total))

    async def heartbeat(self) -> None:
        interval = 0.1
        while True:
            t = time.monotonic()
            await asyncio.sleep(interval)
            lag = time.monotonic() - t - interval
            self.stage_lag = max(self.stage_lag, lag)
            if lag > 0.1:
                self.log.info("ui_stall", extra={"data": {"ms": round(lag * 1000), "stage": self.stage}})
            self.clock.text = (f"Elapsed {time.monotonic() - self.started:5.0f} s · "
                               f"UI delay this stage ≤ {self.stage_lag * 1000:.0f} ms")

    # --- actions -------------------------------------------------------------------
    def on_run(self, widget) -> None:
        if not self.ack.value:
            self.status.text = "Please confirm non-commercial use first."
            return
        if not self.settings.get("engine_license_ack"):
            self.settings.update(engine_license_ack=True,
                                 engine_license_ack_time=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
            self._save_settings()
        self.start_pipeline()

    def on_open(self, widget) -> None:
        if self.server:
            webbrowser.open(self.server.url)

    def start_pipeline(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        self.run_button.enabled = False
        self.worker = threading.Thread(target=self.pipeline, name="pipeline", daemon=True)
        self.worker.start()

    def pipeline(self) -> None:
        activity = begin_activity("Setting up SpliceAI and running a prediction")
        self.log.info("activity", extra={"data": {"began": activity is not None}})
        try:
            env_dir = paths.engine_env(self.base)
            if not engine_ready(env_dir, paths.ENGINE_LOCK):
                self.set_stage("Installing the SpliceAI engine (about 330 MB download)…")
                t = time.monotonic()
                install_engine(
                    find_uv(), paths.ENGINE_LOCK, env_dir, self.base, self.procs,
                    on_output=self._install_output,
                    on_attempt=lambda n, m: self.set_stage(
                        f"Installing the SpliceAI engine — attempt {n} of {m}…"),
                )
                self.log.info("engine_installed", extra={"data": {"seconds": round(time.monotonic() - t, 1)}})

            self.set_stage("Downloading GRCh38 chromosome 17 (26 MB)…", determinate=True)
            fasta = ensure_chromosome("chr17", self.base, progress=self.set_fraction)

            self.set_stage("Running SpliceAI on the demo variant…")
            results = self.run_demo(env_dir, fasta)

            self.server = ResultServer(results, on_quit=lambda: self.ui(self.request_exit))
            self.log.info("result_ready", extra={"data": {
                "url_port": self.server.port,
                "spawn_ms": [(n, round(t * 1000)) for n, t in self.procs.spawn_seconds]}})
            self.set_stage("Done. The prediction is shown in your browser.")
            self.ui(self._finished)
            if not os.environ.get("BIOBRIDGE_NO_BROWSER"):
                webbrowser.open(self.server.url)
        except Cancelled:
            self.log.info("pipeline_cancelled")
        except Exception as exc:
            self.log.info("pipeline_failed", extra={"data": {"error": f"{type(exc).__name__}: {exc}",
                                                             "traceback": traceback.format_exc()}})
            hint = "Check your internet connection, then press Retry." if isinstance(exc, (InstallError, OSError)) else ""
            self.set_stage(f"Failed: {exc}. {hint}")
            self.ui(self._failed)
        finally:
            end_activity(activity)

    def _install_output(self, line: str) -> None:
        self.log.info("install_output", extra={"data": {"line": line}})
        if line:
            self.set_detail(line)

    def _finished(self) -> None:
        self.progress.stop()
        self.progress.max, self.progress.value = 1.0, 1.0
        self.open_button.enabled = True

    def _failed(self) -> None:
        self.progress.stop()
        self.run_button.text = "Retry"
        self.run_button.enabled = True

    def run_demo(self, env_dir: Path, fasta: Path) -> dict:
        job = self.base / "jobs" / time.strftime("%Y%m%d-%H%M%S")
        job.mkdir(parents=True, exist_ok=True)
        vcf = job / "input.vcf"
        vcf.write_text(
            "##fileformat=VCFv4.2\n##contig=<ID=chr17,length=83257441>\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
            f"{DEMO['chrom']}\t{DEMO['pos']}\t{DEMO['id']}\t{DEMO['ref']}\t{DEMO['alt']}\t.\t.\t.\n"
        )
        request = {"schema": "biobridge.spliceai.request/1", "vcf": str(vcf), "annotation": "grch38",
                   "distance": 50, "reference": {"chr17": str(fasta)}}
        (job / "request.json").write_text(json.dumps(request))
        with (job / "runner.log").open("w") as log:
            proc = self.procs.spawn(
                [env_dir / "bin" / "python", paths.RUNNER, "score",
                 "--request", job / "request.json", "--out", job / "results.json"],
                env=sanitized_env(self.base), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=log, text=True, bufsize=1)
            for line in proc.stdout:
                event = json.loads(line)
                if event["event"] == "stage":
                    self.set_detail({"loading_model": "Loading the model…",
                                     "scoring": "Scoring…"}.get(event["stage"], event["stage"]))
                elif event["event"] == "error":
                    raise RuntimeError(event["message"])
            rc = proc.wait()
        if self.procs.closing:
            raise Cancelled("BioBridge is quitting")
        if rc != 0:
            raise RuntimeError(f"SpliceAI runner exited with code {rc}; see {job / 'runner.log'}")
        results = json.loads((job / "results.json").read_text())
        results["reference_md5"] = {"chr17": (fasta.with_name(fasta.name + ".md5")).read_text()}
        return results

    # --- quit ----------------------------------------------------------------------
    def handle_exit(self, app, **kwargs) -> bool:
        t = time.monotonic()
        pids = self.procs.pids
        running = self.procs.terminate_all(grace=3.0)
        if self.server:
            self.server.close()
        survivors = [pid for pid in pids if alive(pid)]
        self.log.info("quit_cleanup", extra={"data": {
            "children_started": len(pids), "groups_running_at_quit": running,
            "survivors": survivors, "seconds": round(time.monotonic() - t, 2),
        }})
        return True


def main() -> BioBridge:
    return BioBridge("BioBridge", "local.biobridge.biobridge")
