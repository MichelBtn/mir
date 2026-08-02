import io
import logging
import socket
import time
import threading
import numpy as np
from flask import Flask, Response, jsonify, request
from waitress import serve
# pyrefly: ignore [missing-import]
from lidar import LidarSensor
# pyrefly: ignore [missing-import]
from discovery_responder import DiscoveryResponder

logging.basicConfig(level=logging.INFO)


# ─── Buffer partagé (calqué sur StreamingOutput caméra) ───────────────────────
class LidarOutput:

    def __init__(self):
        self.frame = None          # bytes bruts du scan (format npy)
        self.last_updated = time.time()
        self.event = threading.Event()

    def write(self, scan: np.ndarray):
        buf = io.BytesIO()
        np.save(buf, scan)         # sérialisation numpy native
        self.frame = buf.getvalue()
        self.last_updated = time.time()
        self.event.set()
        self.event.clear()

# ─── Système LiDAR (calqué sur CameraSystem) ──────────────────────────────────
class LidarSystem:

    def __init__(self, id="lidar", port=8081, device="/dev/ttyUSB0"):
        self._id = id
        self._port = port
        self._device = device
        self._config = {"filter_distance": None}

        self.output = LidarOutput()
        self.app = Flask(__name__)

        self.stream_path = "/stream"
        self.app.add_url_rule(self.stream_path, view_func=self.stream_data)
        self.app.add_url_rule("/config",        view_func=self.get_config, methods=["GET"])
        self.app.add_url_rule("/config",        view_func=self.set_config, methods=["PATCH"])
        self.app.add_url_rule("/status",        view_func=self.get_status, methods=["GET"])

    # ── Thread LiDAR ──────────────────────────────────────────────────────────

    def _lidar_thread(self):
        sensor = LidarSensor(self._device)
        sensor.connect()
        logging.info("LiDAR connecté")
        try:
            for scan in sensor.iter_scans_to_array():
                if self._config["filter_distance"] is not None:
                    scan = scan[scan[:, 1] <= self._config["filter_distance"]]
                self.output.write(scan)    # même interface que StreamingOutput
        finally:
            sensor.disconnect()

    # ── Générateur de flux (calqué sur _generate_frames caméra) ───────────────
    def _generate_frames(self):
        logging.info("Nouveau client connecté au flux LiDAR")
        try:
            while True:
                triggered = self.output.event.wait(timeout=5.0)  # bloquant jusqu'au prochain scan
                if not triggered:
                    continue  # timeout = pas de données, on reboucle
                frame = self.output.frame
                if frame:
                    header = (
                        "--FRAME\r\n"
                        "Content-Type: application/octet-stream\r\n"
                        f"Content-Length: {len(frame)}\r\n\r\n"
                    )
                    yield header.encode() + frame + b"\r\n"
        except GeneratorExit:
            logging.info("Client déconnecté du flux LiDAR")

    # ── Routes Flask ───────────────────────────────────────────────────────────

    def stream_data(self):
        return Response(
            self._generate_frames(),
            mimetype="multipart/x-mixed-replace; boundary=FRAME",
        )

    def get_config(self):
        return jsonify(self._config)

    def set_config(self):
        try:
            data = request.get_json()
            for key, value in data.items():
                if key in self._config:
                    self._config[key] = value
            return jsonify({"status": "ok", "config": self._config})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    def get_status(self):
        return jsonify({"config": self._config})

    # ── Utilitaire ────────────────────────────────────────────────────────────

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "0.0.0.0"

    # ── Démarrage ─────────────────────────────────────────────────────────────

    def start(self):
        ip = self._get_local_ip()

        self._discovery = DiscoveryResponder(profile={
            "id": self._id, "type": "pi_lidar", "ip": ip, "port": self._port,
        })
        self._discovery.start()

        threading.Thread(target=self._lidar_thread, daemon=True).start()

        logging.info("======== Serveur LiDAR démarré ========")
        logging.info(f"     └── Stream → http://{ip}:{self._port}{self.stream_path}")
        logging.info(f"     └── Config → http://{ip}:{self._port}/config")

        serve(self.app, host="0.0.0.0", port=self._port, threads=4)


if __name__ == "__main__":
    LidarSystem(id="lidar_default", port=8081, device='/dev/ttyUSB0').start()
    