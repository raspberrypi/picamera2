import threading
import time

from app_full import app, window


def test_func():
    time.sleep(5)
    app.quit()


thread = threading.Thread(target=test_func, daemon=True)
thread.start()

window.show()
app.exec()
