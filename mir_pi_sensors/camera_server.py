import io
import logging
import socket
import time
from flask import Flask, Response, jsonify, request
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput
from waitress import serve
import json
import numpy as np
# pyrefly: ignore [missing-import]
from discovery_responder import DiscoveryResponder

def to_jsonable(obj):
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]

    if isinstance(obj, (np.integer,)):
        return int(obj)

    if isinstance(obj, (np.floating,)):
        return float(obj)

    if isinstance(obj, np.ndarray):
        return obj.tolist()
    # Dernier recours : convertir en string
    if not isinstance(obj, (str, int, float, bool)) and obj is not None:
        return str(obj)

    return obj


logging.basicConfig(level=logging.INFO)



# ─── Buffer MJPEG partagé ─────────────────────────────────────────────────────
class StreamingOutput(io.BufferedIOBase):

    def __init__(self):
        self.frame = None
        # Utilisation d'un timestamp pour éviter les blocages ou la surconsommation CPU
        self.last_updated = time.time()

    # pyrefly: ignore [bad-override]
    def write(self, buffer):
        self.frame = buffer
        self.last_updated = time.time()


# ─── Système de Caméra Principal (Composition - Port Unique) ──────────────────
class CameraSystem:

    def __init__(self, default_id, width=640, height=480, port=8080):
        # 1. Matériel
        self.picam2 = Picamera2()
        self._sensor_modes = self.picam2.sensor_modes
        self._width = width
        self._height = height
        self._port = port
        configuration = self.picam2.create_video_configuration(main={"size": (width, height)})
        self.picam2.configure(
            configuration
        )
        self._load_settings(default_id)

        # 3. Composants
        self.output = StreamingOutput()
        self.app = Flask(__name__)

        # Enregistrement de TOUTES les routes sur le même serveur Flask
        self.stream_path = "/stream.mjpg"
        self.settings_path = "/settings"
        self.app.add_url_rule(self.settings_path, view_func=self.get_settings, methods=["GET"])
        self.app.add_url_rule(self.settings_path, view_func=self.set_settings, methods=["PATCH"])
        self.app.add_url_rule("/schema", view_func=self.get_schema, methods=["GET"])
        self.app.add_url_rule("/actual_controls", view_func=self.get_actual_controls, methods=["GET"])        
        self.app.add_url_rule(self.stream_path, view_func=self.stream_video)
        self.app.add_url_rule("/camera/<resource>", view_func=self.get_camera_info,methods=["GET"])
        self.app.add_url_rule("/restart", view_func=self.restart, methods=["POST"])

    def restart(self):
        logging.info("Restart requested by client. Exiting to allow systemd restart.")
        def perform_restart():
            time.sleep(0.5)
            import os
            os._exit(1)
        import threading
        threading.Thread(target=perform_restart, daemon=True).start()
        return jsonify({"status": "ok", "message": "Restarting"})

    def get_camera_info(self, resource):
        if resource == "controls":
            return jsonify(dict(self.picam2.camera_controls))
        elif resource == "metadata":
            return jsonify(dict(self.picam2.capture_metadata()))
        elif resource == "sensor_modes":
            return jsonify(to_jsonable(self._sensor_modes))
        else:
            return jsonify({"error": "ressource inconnue"}), 404
        
    def get_schema(self):
        camera_controls = dict(self.picam2.camera_controls)
        return jsonify({
            "AeEnable": camera_controls["AeEnable"],
            "ExposureTime": camera_controls["ExposureTime"],
        })


    def get_actual_controls(self):
        meta = self.picam2.capture_metadata()
        return jsonify(dict(meta))

    def get_settings(self):
        return jsonify(self._settings)

    def _save_settings(self):
        try:
            with open("settings.json", "w") as f:
                json.dump(self._settings, f)
        except Exception as e:
            logging.warning(f"Impossible de sauvegarder les contrôles : {e}")

    def _load_settings(self, default_id):
        self._settings = {
            "id": default_id,
            "AeEnable": False,
            "ExposureTime": 10000,
            "FrameDurationLimits": (33333, 33333)
        }
        try:
            with open("settings.json", "r") as f:
                data = json.load(f)
                for key, value in data.items():
                    if key in self._settings:
                        if key == "ExposureTime":
                            self._settings[key] = int(value)
                        else:
                            self._settings[key] = value
        except Exception as e:
            logging.warning(f"Erreur au chargement de settings : {e}")

    def apply_controls(self):
        try:
            logging.info(f"Current exposure settings: AeEnable={self._settings['AeEnable']} ExposureTime={self._settings['ExposureTime']}")
            if self._settings["AeEnable"]:
                self.picam2.set_controls({
                    "AeEnable": True, 
                    "FrameDurationLimits": self._settings["FrameDurationLimits"]})
            else:
                self.picam2.set_controls({
                    "AeEnable": False, 
                    "ExposureTime": int(self._settings["ExposureTime"]), 
                    "FrameDurationLimits": self._settings["FrameDurationLimits"]})
            self._save_settings()   
        except Exception as e:
            logging.info(f"Echec apply_settings : {e}")

    def set_settings(self):
        try:
            data = request.json
            logging.info(f"set_settings : {data}")
            for key, value in data.items():
                if key in self._settings:
                    if key == "id":
                        self._settings[key] = value
                        self._save_settings()
                        self._profile["id"] = value
                        self._discovery.update_profile(self._profile)   
                    elif key == "ExposureTime":
                        self._settings[key] = int(value)
                        self.apply_controls()
                    elif key == "AeEnable":
                        if not isinstance(value, bool):
                            raise ValueError(f"AeEnable doit être un booléen, reçu : {type(value).__name__}")
                        self._settings[key] = value
                        self.apply_controls()
                    elif key == "FrameDurationLimits":
                        if not isinstance(value, list) or len(value) != 2:
                            raise ValueError("FrameDurationLimits doit être un tableau de 2 entiers")
                        self._settings[key] = (int(value[0]), int(value[1]))
                        self.apply_controls()
            return jsonify({"status": "ok", "settings": self._settings})            
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    def _generate_frames(self):
        """Générateur de flux qui lit le buffer et formate les paquets MJPEG."""
        logging.info("Nouveau client connecté au flux vidéo")
        last_frame_time = 0
        try:
            while True:
                # Si une nouvelle image est disponible dans le buffer
                if self.output.last_updated > last_frame_time:
                    frame = self.output.frame
                    last_frame_time = self.output.last_updated

                    if frame:
                        # Formatage propre : tout est en chaîne de caractères (str)
                        chaine_complete = (
                            "--FRAME\r\n"
                            "Content-Type: image/jpeg\r\n"
                            f"Content-Length: {len(frame)}\r\n\r\n"
                        )

                        # On encode l'ensemble en bytes d'un seul coup, puis on ajoute les données binaires de l'image
                        yield chaine_complete.encode("utf-8") + frame + b"\r\n"
                else:
                    # Petite pause pour soulager le CPU si l'image n'a pas changé
                    time.sleep(0.01)
        except GeneratorExit:
            logging.info("Client déconnecté du flux vidéo")

    def stream_video(self):
        """Route Flask qui distribue le flux vidéo continu."""
        return Response(
            self._generate_frames(),
            mimetype="multipart/x-mixed-replace; boundary=FRAME",
        )

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "0.0.0.0"

    def start(self):
        ip = self.get_local_ip()
        self._profile = {
            "id":      self._settings.get("id", "cam_default"),
            "type":    "pi_camera",
            "ip":      ip,
            "port":    self._port,
            "width":   self._width,
            "height":  self._height,
            "fps": 0
        }
        self._discovery = DiscoveryResponder(profile=self._profile)
        self._discovery.start()

        # Démarrage de la capture
        self.picam2.start_recording(MJPEGEncoder(), FileOutput(self.output))
        logging.info("======== Serveur démarré ========")
        logging.info(f"     └── Vidéo     → http://{ip}:{self._port}{self.stream_path}")
        logging.info(f"     └── Settings  → http://{ip}:{self._port}{self.settings_path}")

        self.apply_controls()
        meta = self.picam2.capture_metadata()
        self._profile["fps"] = meta["FrameDuration"]
        # Démarrage du serveur Flask
        # Waitress gère nativement le multi-threading.
        # On passe 'threads=4' (ou plus) pour s'assurer qu'un client qui regarde
        # la vidéo ne bloque pas les requêtes de configuration d'un autre outil.
        serve(self.app, host="0.0.0.0", port=self._port, threads=4)


# ─── Point d'entrée ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    cam_sys = CameraSystem(default_id="cam_default", width=640, height=480, port=8080)
    cam_sys.start()

