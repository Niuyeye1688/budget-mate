import sys

if sys.platform == "win32" and getattr(sys, "frozen", False):
    import ctypes
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

import threading
import time
import socket
import webview
from app import app


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def run_flask(port):
    app.run(debug=False, host="127.0.0.1", port=port, use_reloader=False)


def wait_for_server(port, timeout=30):
    for _ in range(int(timeout * 10)):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.1)
            s.connect(("127.0.0.1", port))
            s.close()
            return True
        except Exception:
            time.sleep(0.1)
    return False


if __name__ == "__main__":
    port = get_free_port()
    t = threading.Thread(target=run_flask, args=(port,), daemon=True)
    t.start()
    if not wait_for_server(port):
        import sys
        sys.exit(1)
    window = webview.create_window(
        "经费审批与记账助手",
        f"http://127.0.0.1:{port}",
        width=1280,
        height=800,
    )
    webview.start()
