import numpy as np
from numpy.typing import NDArray
import io
import requests
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import threading
from typing import Any

class LidarSensorIP():
    def __init__(self, ip, port=8081):
        self._url = f"http://{ip}:{port}/stream"
        self._last_scan:NDArray[Any]|None = None
        self._scan_lock = threading.Lock()
        self._bg_running = False

    def iter_scans(self):
        boundary = b"--FRAME"
        buf = b""

        with requests.get(self._url, stream=True) as r:
            for chunk in r.iter_content(chunk_size=8192):
                buf += chunk

                while True:
                    # Cherche deux boundaries consécutifs qui délimitent un frame complet
                    start = buf.find(boundary)
                    if start == -1:
                        break
                    end = buf.find(boundary, start + len(boundary))
                    if end == -1:
                        break  # frame pas encore complet, on attend plus de données

                    frame_block = buf[start + len(boundary):end]
                    buf = buf[end:]  # avance le buffer

                    # Sépare header et body
                    if b"\r\n\r\n" not in frame_block:
                        continue
                    _, body = frame_block.split(b"\r\n\r\n", 1)
                    body = body.rstrip(b"\r\n")

                    if body:
                        yield np.load(io.BytesIO(body))

    def get_last_scan(self) -> NDArray[Any]|None:
        if not self._bg_running:
            raise RuntimeError("get_last_scan() impossible : appeler start_background_scan() avant")
        with self._scan_lock:
            return self._last_scan
    
    def start_background_scan(self):
        self._bg_running = True
        def _worker():
            for scan in self.iter_scans():
                if not self._bg_running:
                    break
                with self._scan_lock:
                    self._last_scan = scan
        self._bg_thread = threading.Thread(target=_worker, daemon=True)
        self._bg_thread.start()

    def stop_background_scan(self):
        self._bg_running = False
        if hasattr(self, '_bg_thread'):
            self._bg_thread.join(timeout=2)


if __name__ == "__main__":
    lidar = LidarSensorIP("192.168.1.22")
    lidar.start_background_scan()

    fig, ax = plt.subplots(subplot_kw={'projection': 'polar'}, figsize=(6, 6))
    sc = ax.scatter([], [], s=2, alpha=0.8)
    
    ax.set_title('RPLIDAR C1', va='bottom', pad=20)
    # pyrefly: ignore [missing-attribute]
    ax.set_theta_zero_location('N')
    # pyrefly: ignore [missing-attribute]
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 2500)

    # Fonction de mise à jour appelée automatiquement par FuncAnimation
    def update(frame):
        scan = lidar.get_last_scan()
        if scan is not None:
            angles_rad = np.deg2rad(scan[:, 0])
            distances = scan[:, 1]
            sc.set_offsets(np.c_[angles_rad, distances])
        return sc,

    # Gestion de la fermeture proprement
    def on_close(event):
        lidar.stop_background_scan()
        print("closed")

    fig.canvas.mpl_connect('close_event', on_close)

    # Remplacement de la boucle while (intervalle en millisecondes)
    ani = FuncAnimation(fig, update, interval=50, blit=True, cache_frame_data=False)

    plt.show()

    