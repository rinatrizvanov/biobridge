"""Run the web interface with uvicorn on 127.0.0.1 in a background thread."""

from __future__ import annotations

import socket
import threading

import uvicorn

from biobridge.web.app import BioBridgeWeb


class WebServer:
    def __init__(self, make_web) -> None:
        """`make_web(allowed_host)` builds the BioBridgeWeb once the port is known."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.web: BioBridgeWeb = make_web(f"127.0.0.1:{self.port}")
        config = uvicorn.Config(self.web.app, log_level="warning", lifespan="off", access_log=False)
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, kwargs={"sockets": [self.sock]},
                                       name="web-server", daemon=True)

    def start(self) -> "WebServer":
        self.thread.start()
        return self

    def stop(self, timeout: float = 5.0) -> None:
        self.web.manager.shutdown()
        self.server.should_exit = True
        self.thread.join(timeout)
        self.sock.close()
