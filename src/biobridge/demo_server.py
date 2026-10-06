"""Localhost page showing the spike's single real prediction.

Binds to 127.0.0.1 on a random port. Every request must carry the per-launch token
and a Host header naming that address, so other local pages or DNS-rebinding sites
cannot read the result or trigger Quit.
"""

from __future__ import annotations

import html
import secrets
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

FIELDS = ["DS_AG", "DS_AL", "DS_DG", "DS_DL"]


class ResultServer:
    def __init__(self, results: dict, on_quit: Callable[[], None]) -> None:
        self.token = secrets.token_urlsafe(24)
        self.results = results
        self.on_quit = on_quit
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _handler(self))
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}/?t={self.token}"
        threading.Thread(target=self.httpd.serve_forever, name="result-server", daemon=True).start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def allowed(self, handler: BaseHTTPRequestHandler) -> bool:
        query = parse_qs(urlparse(handler.path).query)
        host_ok = handler.headers.get("Host") == f"127.0.0.1:{self.port}"
        token_ok = secrets.compare_digest(query.get("t", [""])[0], self.token)
        return host_ok and token_ok


def _handler(server: ResultServer):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if not server.allowed(self) or urlparse(self.path).path != "/":
                self.send_error(403)
                return
            self._send(200, render(server.results, server.token))

        def do_POST(self):
            if not server.allowed(self) or urlparse(self.path).path != "/quit":
                self.send_error(403)
                return
            self._send(200, "<!doctype html><title>BioBridge</title><p>BioBridge is quitting. You can close this tab.</p>")
            server.on_quit()

        def _send(self, status: int, body: str) -> None:
            data = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

    return Handler


def _fmt(value) -> str:
    return "NA" if value is None else f"{value:.2f}" if isinstance(value, float) else str(value)


def render(results: dict, token: str) -> str:
    e = html.escape
    rows = []
    for rec in results["records"]:
        for allele in rec["alleles"]:
            variant = f"{rec['chrom']}:{rec['pos']} {rec['ref']}>{allele['alt']}"
            if allele["status"] != "SCORED":
                rows.append(f"<tr><td>{e(variant)}</td><td colspan=10>Not scored: {e(allele.get('reason', ''))}</td></tr>")
                continue
            for gene in allele["genes"]:
                for mode in ("masked", "raw"):
                    s = gene[mode]
                    cells = "".join(f"<td>{_fmt(s[f])}</td>" for f in FIELDS)
                    positions = "".join(
                        f"<td>{rec['chrom']}:{rec['pos'] + s['DP_' + f[3:]]:,}</td>" for f in FIELDS)
                    rows.append(f"<tr><td>{e(variant)}</td><td>{e(gene['gene'])}</td><td>{mode}</td>{cells}{positions}</tr>")
    eng = results["engine"]
    models = "".join(f"<li><code>{e(k)}</code> {e(v[:16])}…</li>" for k, v in eng["models_sha256"].items())
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BioBridge result</title>
<style>
 body {{ font: 15px/1.45 -apple-system, system-ui, sans-serif; margin: 24px; color: #1d1d1f; background: #fff; }}
 .warn {{ border: 1px solid #c77700; background: #fff6e5; padding: 10px 14px; border-radius: 6px; max-width: 70em; }}
 table {{ border-collapse: collapse; margin: 16px 0; }} td, th {{ border: 1px solid #ccc; padding: 4px 8px; text-align: right; }}
 td:first-child, td:nth-child(2), td:nth-child(3), th {{ text-align: left; }}
 @media (prefers-color-scheme: dark) {{ body {{ background: #1d1d1f; color: #f5f5f7; }} .warn {{ background: #3a2a00; }} }}
</style></head><body>
<h1>BioBridge — one real SpliceAI prediction</h1>
<p class="warn"><strong>Experimental feasibility build. Not a diagnostic.</strong>
The variant is a synthetic test variant at a real GRCh38 position, not a clinical example.
Delta scores are SpliceAI's predicted change in splice-site probability within ±50 nt; they are not
confidence levels. Missing values are shown as NA, never 0.</p>
<table><tr><th>Variant</th><th>Gene (SpliceAI annotation)</th><th>Mode</th>
<th>DS_AG</th><th>DS_AL</th><th>DS_DG</th><th>DS_DL</th>
<th>AG position</th><th>AL position</th><th>DG position</th><th>DL position</th></tr>
{''.join(rows)}</table>
<h2>Provenance</h2>
<ul><li>spliceai {e(eng['spliceai'])}, TensorFlow {e(eng['tensorflow'])}, Keras {e(eng['keras'])}, Python {e(eng['python'])}</li>
<li>Annotation {e(eng['annotation'])} (GENCODE V24 canonical, bundled with spliceai), sha256 {e(str(eng['annotation_sha256'])[:16])}…</li>
<li>Reference: UCSC hg38 chr17, md5 {e(results.get('reference_md5', {}).get('chr17', 'unknown'))}</li>
<li>Settings: distance {results['settings']['distance']}, masked and raw</li>
<li>Models (CC BY-NC 4.0, Illumina): <ul>{models}</ul></li></ul>
<form method="post" action="/quit?t={e(token)}"><button type="submit">Quit BioBridge</button></form>
</body></html>"""
