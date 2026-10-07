"""The local web interface.

Security (BioBridge listens on 127.0.0.1 only, but other local software and web
pages must not be able to use it):
- The Host header must name BioBridge's own address (stops DNS rebinding).
- The launcher opens /auth?t=<one-time token>; the token is exchanged for an
  HttpOnly, SameSite=Strict session cookie, so it never stays in the address bar.
- Every other request needs that cookie. POST requests also need a matching Origin
  header and the session's CSRF field.
- No CORS headers; a strict Content-Security-Policy (no inline script or style).
- Upload size is checked from Content-Length before the form is parsed.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import tempfile
from collections.abc import Callable
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from biobridge import __version__
from biobridge.explain import ABOUT, LIMITATIONS, event_table, explain
from biobridge.inputs.text import EXAMPLE, InputError, parse_variant
from biobridge.inputs.upload import MAX_UPLOAD_BYTES, prepare_upload
from biobridge.jobs.job import MAX_ALLELES, JobRequest
from biobridge.results import EVENT_NAMES, cutoff_band, short_allele
from biobridge.web.jobs import Busy, JobManager
from biobridge.web.plot import four_score_svg

HERE = Path(__file__).parent
COOKIE = "bb_session"
MAX_BODY_BYTES = MAX_UPLOAD_BYTES + (256 << 10)  # file limit plus form overhead
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                               "form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
    "X-Content-Type-Options": "nosniff",
    # "same-origin", not "no-referrer": with no-referrer, browsers send "Origin: null" on form
    # POSTs (Fetch spec), which the Origin check must reject. Verified in Chromium and WebKit.
    "Referrer-Policy": "same-origin",
    "X-Frame-Options": "DENY",
    "Cache-Control": "no-store",
}


class BioBridgeWeb:
    def __init__(self, manager: JobManager, allowed_host: str,
                 on_quit: Callable[[], None] | None = None) -> None:
        self.manager = manager
        self.allowed_host = allowed_host
        self.on_quit = on_quit
        self.session = secrets.token_urlsafe(32)
        self.csrf = hmac.new(self.session.encode(), b"csrf", hashlib.sha256).hexdigest()
        self._tokens: set[str] = set()
        self.templates = Jinja2Templates(directory=str(HERE / "templates"))
        self.templates.env.globals.update(version=__version__, example=EXAMPLE, max_alleles=MAX_ALLELES,
                                          event_names=EVENT_NAMES, csrf=self.csrf)
        self.templates.env.filters["allele"] = short_allele
        self.app = Starlette(routes=[
            Route("/auth", self.auth),
            Route("/", self.index),
            Route("/jobs", self.submit, methods=["POST"]),
            Route("/jobs/{job_id}", self.job_page),
            Route("/jobs/{job_id}/status", self.status),
            Route("/jobs/{job_id}/cancel", self.cancel, methods=["POST"]),
            Route("/jobs/{job_id}/results.csv", self.download),
            Route("/quit", self.quit, methods=["POST"]),
            Mount("/static", app=StaticFiles(directory=str(HERE / "static")), name="static"),
        ])
        self.app.add_middleware(_Guard, web=self)

    def mint_token(self) -> str:
        token = secrets.token_urlsafe(24)
        self._tokens.add(token)
        return token

    def auth_url(self) -> str:
        return f"http://{self.allowed_host}/auth?t={self.mint_token()}"

    # --- routes ----------------------------------------------------------------------
    async def auth(self, request: Request) -> Response:
        token = request.query_params.get("t", "")
        if token not in self._tokens:
            return _forbidden("This link has already been used. Use “Open in browser” in the BioBridge window.")
        self._tokens.discard(token)  # one-time
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(COOKIE, self.session, httponly=True, samesite="strict", path="/")
        return response

    def _render(self, request: Request, name: str, status_code: int = 200, **context) -> Response:
        return self.templates.TemplateResponse(request, name, context, status_code=status_code)

    async def index(self, request: Request, error: str | None = None, status_code: int = 200) -> Response:
        current = self.manager.current
        running = current if current and current.status == "running" else None
        return self._render(request, "index.html", status_code, error=error, running=running)

    async def submit(self, request: Request) -> Response:
        length = request.headers.get("content-length")
        if length is None:
            return await self.index(request, "The upload did not state its size; please try again.", 411)
        if int(length) > MAX_BODY_BYTES:
            return await self.index(request, f"The file is too large; the limit is "
                                             f"{MAX_UPLOAD_BYTES / (1 << 20):.1f} MB.", 413)
        form = await request.form(max_files=1, max_fields=8)
        if not hmac.compare_digest(str(form.get("csrf", "")), self.csrf):
            return _forbidden("The form has expired. Reload the page and try again.")
        variant = str(form.get("variant") or "").strip()
        upload = form.get("vcf")
        data = await upload.read(MAX_UPLOAD_BYTES + 1) if upload is not None and getattr(upload, "filename", "") else b""
        try:
            if bool(variant) == bool(data):
                raise InputError("Enter one variant or choose one VCF file (not both).")
            if form.get("confirm_grch38") != "yes":
                raise InputError("Please confirm that the coordinates are GRCh38 (hg38).")
            if variant:
                parse_variant(variant)
            else:
                with tempfile.TemporaryDirectory() as tmp:  # fast checks before queueing
                    prepare_upload(data, Path(tmp) / "check.vcf")
            state = self.manager.submit(JobRequest(
                paste=variant or None, vcf_bytes=data or None,
                vcf_name=(Path(upload.filename).name if data else None), confirm_grch38=True))
        except InputError as exc:
            return await self.index(request, str(exc), 400)
        except Busy:
            return await self.index(request, "A job is already running. Wait for it to finish or cancel it.", 409)
        finally:
            if upload is not None and hasattr(upload, "close"):
                await upload.close()
        return RedirectResponse(f"/jobs/{state.id}", status_code=303)

    async def job_page(self, request: Request) -> Response:
        state = self.manager.get(request.path_params["job_id"])
        if state is None:
            return HTMLResponse("Not found", status_code=404)
        context = {"job": state}
        if state.status == "done" and state.result:
            context.update(results_context(state.result))
        return self._render(request, "job.html", **context)

    async def status(self, request: Request) -> Response:
        state = self.manager.get(request.path_params["job_id"])
        if state is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        p = state.progress
        return JSONResponse({"status": state.status, "stage": p.stage, "message": p.message,
                             "done": p.done, "total": p.total, "error": state.error})

    async def cancel(self, request: Request) -> Response:
        form = await request.form(max_files=0, max_fields=2)
        if not hmac.compare_digest(str(form.get("csrf", "")), self.csrf):
            return _forbidden("The form has expired. Reload the page and try again.")
        self.manager.cancel(request.path_params["job_id"])
        return RedirectResponse(f"/jobs/{request.path_params['job_id']}", status_code=303)

    async def download(self, request: Request) -> Response:
        state = self.manager.get(request.path_params["job_id"])
        if state is None or state.result is None:
            return HTMLResponse("Not found", status_code=404)
        return FileResponse(state.result.csv_path, media_type="text/csv",
                            filename=f"biobridge-{state.result.job_dir.name}.csv")

    async def quit(self, request: Request) -> Response:
        form = await request.form(max_files=0, max_fields=2)
        if not hmac.compare_digest(str(form.get("csrf", "")), self.csrf):
            return _forbidden("The form has expired. Reload the page and try again.")
        if self.on_quit:
            self.on_quit()
        return self._render(request, "quit.html")


def results_context(result) -> dict:
    rows = result.rows
    genes_per_allele: dict[tuple, int] = {}
    for row in rows:
        key = (row.record, row.alt)
        genes_per_allele[key] = genes_per_allele.get(key, 0) + (1 if row.gene else 0)
    views = []
    for i, row in enumerate(rows):
        top = row.top_masked()
        views.append({
            "row": row, "uid": f"r{i}",
            "top": top, "band": cutoff_band(top[0]) if top else None,
            "explanation": explain(row, genes_per_allele.get((row.record, row.alt), 1)),
            "events": event_table(row) if row.gene and row.status == "SCORED" else [],
            "plot": four_score_svg(row, f"p{i}") if row.status == "SCORED" else "",
        })
    prov = result.provenance
    return {"views": views, "summary": result.summary, "provenance": prov, "about": ABOUT,
            "limitations": LIMITATIONS, "mock": bool(prov.get("engine_mock"))}


def _forbidden(message: str) -> Response:
    return HTMLResponse(f"<!doctype html><meta charset=utf-8><title>BioBridge</title><p>{message}</p>",
                        status_code=403)


class _Guard:
    """ASGI middleware enforcing host, session, origin and security headers."""

    def __init__(self, app, web: BioBridgeWeb) -> None:
        self.app, self.web = app, web

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request = Request(scope)
        if request.headers.get("host") != self.web.allowed_host:
            return await _with_headers(HTMLResponse("Bad request", status_code=400))(scope, receive, send)
        if scope["path"] != "/auth":
            cookie = request.cookies.get(COOKIE, "")
            if not hmac.compare_digest(cookie, self.web.session):
                response = _forbidden("Open BioBridge from its window (“Open in browser”).")
                return await _with_headers(response)(scope, receive, send)
            if scope["method"] not in ("GET", "HEAD") and \
                    request.headers.get("origin") != f"http://{self.web.allowed_host}":
                return await _with_headers(_forbidden("Request blocked."))(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", [])
                           if k.decode().lower() not in {h.lower() for h in SECURITY_HEADERS}]
                headers += [(k.lower().encode(), v.encode()) for k, v in SECURITY_HEADERS.items()]
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


def _with_headers(response: Response) -> Response:
    for key, value in SECURITY_HEADERS.items():
        response.headers[key] = value
    return response
