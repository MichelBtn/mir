from dataclasses import dataclass
import cv2
from threading import Event, Lock, Thread
import os
import numpy as np
from lerobot.cameras import ColorMode
from typing import Any
from numpy.typing import NDArray
import time
from mir_utils.metrics import SimpleMovingAverage, Stats, RollingArray
from mir_devices.mir_sensor import (mirSensor, 
                                    mirPiCameraConfiguration, 
                                    SensorProperty,
                                    mirSensorConfiguration)
from mir_devices.mir_device import (ObservablePropertyBitmap,
                                    ObservableProperty,
                                    ObservationValue,
                                    ActionValue)
import requests
from loguru import logger
from math import ceil, floor

@dataclass
class mirCameraSettings:
    auto_exposure : bool
    exposure_micro_sec : int

class ImirCamera(mirSensor):
    def send_action(self, actions: dict[str, ActionValue])->dict[str, ActionValue]:
        return {}
    

class CamIP(ImirCamera):
    def __init__(self, sensor_key:str, cfg : mirSensorConfiguration, url:str, frame_stats_size: int = 0):
        super().__init__(sensor_key)
        self._url = url
        self._frames_scope : RollingArray |None = None
        if frame_stats_size > 0:
            self._frames_scope  = RollingArray(frame_stats_size)
            self._frames_scope_lock = Lock()
            self._stats = Stats(10)
        self._sma = SimpleMovingAverage(20)
        self._isconnected = False
        self._thread: Thread | None = None
        self._stop_event: Event = Event()
        self._latest_frame_lock: Lock = Lock()
        self._latest_frame: np.ndarray | None = None
        self._capture: cv2.VideoCapture | None = None

    def mir_is_connected(self) -> bool:
        return self._isconnected

    @staticmethod
    def find_cameras() -> list[dict[str, Any]] :
        """Detects available cameras connected to the system.
        Returns:
            List[Dict[str, Any]]: A list of dictionaries,
            where each dictionary contains information about a detected camera.
        """
        return [{}]

    def mir_connect(self) -> None:
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            "fflags;nobuffer|"
            "flags;low_delay|"
            "analyzeduration;0|"
            "probesize;32|"
        )
        self._capture = cv2.VideoCapture(self._url, cv2.CAP_FFMPEG)
        if not self._capture.isOpened():
            raise ConnectionError(f"Cam_OpenCV failed to open stream: {self._url}")
        self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._start_read()
        self._isconnected = True            

    def mir_disconnect(self) -> None:
        self._stop_read()
        if hasattr(self, '_capture') and self._capture is not None:
            self._capture.release() # type:ignore
        self._isconnected = False

    def get_perfs(self) -> tuple[float, int, np.ndarray, dict|None]:
        if self._frames_scope is None:
            return 0, 0, np.array([]), None
        count, samples = self._frames_scope.get_array()
        return self._sma.average(), count, samples, self._stats.get()
        
    def read(self, color_mode: ColorMode | None = None) -> NDArray[Any]|None:
        with self._latest_frame_lock:
            # Retourne une copie pour éviter des problèmes si le thread modifie l'original
            return self._latest_frame.copy() if self._latest_frame is not None else None
    
    def _start_read(self):
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = Thread(target=self._read_loop, args=(), name="camera_read_loop", daemon=True)
            self._t0 = time.perf_counter()
            self._thread.start()

    def _stop_read(self):
        if self._stop_event is not None:
            self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2)
    
    def _update_stats(self):
        t = time.perf_counter()
        dt = t - self._t0
        self._t0 = t
        self._sma.add(1.0/dt)
        if self._frames_scope is not None:
            self._frames_scope.add(dt)
        self._stats.add(dt*1000)

    def _read_loop(self) -> None:
        while not self._stop_event.is_set():
            if self._capture is None:
                break
            try:
                ret, frame = self._capture.read()
                if not ret or frame is None:
                    continue
                if self._frames_scope is not None:
                    self._update_stats()
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                with self._latest_frame_lock:
                    self._latest_frame = frame_rgb
            except Exception as e:
                print(f"Error reading frame in camera read loop : {e}")        
                break
        self._isconnected = False

    def get_observation(self) -> dict[str, ObservationValue]:
        observation : dict[str, ObservationValue] = {}
        if self.sensor_key in self.subscribed_observations:
            data = self.read()
            if data is not None:
                observation[self.sensor_key] = data
        return observation

class PiCamera(CamIP):
    def __init__(self, sensor_key:str, cfg:mirPiCameraConfiguration):
        self._base_url = f"http://{cfg.ip}:8080"
        stream_url = f"{self._base_url}/stream.mjpg"
        super().__init__(sensor_key, cfg, stream_url, cfg.frame_stats_size if cfg.enable_stats else 0)
        self._configuration = cfg    

    def test_connection(self)->bool:
        if self._isconnected:
            raise RuntimeError("reset_sensor : le capteur est en cours d'utilisation")
        try:
            requests.get(f"{self._base_url}/settings", timeout=(1,1)).json()
            return True
        except Exception:
            return False

    def reset_sensor(self):
        if self._isconnected:
            raise RuntimeError("reset_sensor : le capteur est en cours d'utilisation")
        try:
            response = requests.post(f"{self._base_url}/restart", timeout=(1,1))
            if response.status_code != 200:
                logger.error(f"Failed to restart camera: {response.text}")
        except Exception as e:
            logger.error(f"Failed to restart camera: {e}")
 
    def get_observables(self) -> dict[str, ObservableProperty]:
        return {self.sensor_key : ObservablePropertyBitmap(480, 640, 3)}

    def get_configurable_properties(self) -> dict[str, SensorProperty]:

        """Retourne les propriétés configurables de la caméra"""
        try:
            (min_exposure, max_exposure) = self._get_exposure_range_raw()
            auto_exp, exposure_us = self._get_exposure_raw()
            fps = self._get_fps_raw()
            return {
                "ip" : SensorProperty(
                    label="Adresse IP",
                    tooltip="Adresse IP courante",
                    property_type="str",
                    current_value=self._configuration.ip,
                    requires_reboot=True,
                    read_only=True
                ),
                "exposure_time" : SensorProperty(
                    label="Temps d'exposition (ms)",
                    tooltip=f"Temps d'exposition, en ms, entre {ceil(min_exposure / 1000)} et {floor(max_exposure / 1000)}.",
                    property_type="int",
                    current_value=int(exposure_us / 1000),
                    min_value=int(min_exposure / 1000),
                    max_value=int(max_exposure / 1000),
                    step=1,
                    immediate=True
                ),
                "auto_exposure" : SensorProperty(
                    label="Exposition automatique",
                    property_type="bool",
                    current_value=auto_exp,
                    immediate=True
                ),
                "fps" : SensorProperty(
                    label="FPS",
                    tooltip="Framerate, entre 10 et 60",
                    property_type="int",
                    current_value=int(fps),
                    min_value=10,
                    max_value=60,
                    step=1,
                    immediate=True
                )
            }
        except Exception as e:
            logger.error(f"Failed to get configurable properties: {e}")
            return {}

    def set_property(self, key: str, value: Any) -> bool:
        """Configure une propriété de la caméra"""
        try:
            if key == "ip":
                logger.warning("IP address is not configurable at runtime")
                return False
            elif key == "id":
                self._set_id(str(value))
            elif key == "exposure_time":
                # Convert from ms to microseconds
                exposure_us = int(value) * 1000
                auto_exp, _ = self._get_exposure_raw()
                self._set_exposure_raw(auto_exp, exposure_us)
            elif key == "auto_exposure":
                _, exposure_us = self._get_exposure_raw()
                self._set_exposure_raw(bool(value), exposure_us)
            elif key == "fps":
                self._set_fps_raw(int(value))
            else:
                logger.warning(f"Unknown property: {key}")
                return False
            return True
        except Exception as e:
            logger.error(f"Failed to set property {key}: {e}")
            return False

    def _get_exposure_range_raw(self) -> tuple[int, int]:
        schema = requests.get(f"{self._base_url}/schema").json()
        exposure = schema["ExposureTime"]
        return exposure[0], exposure[1]
    
    def get_actual_settings(self) -> dict:
        return requests.get(f"{self._base_url}/actual_settings").json()
    
    def _get_exposure_raw(self) -> tuple[bool, int]:
        """Get exposure (internal, in microseconds)"""
        settings = requests.get(f"{self._base_url}/settings").json()
        return settings["AeEnable"], settings["ExposureTime"]
    
    def _set_exposure_raw(self, auto_exposure: bool, exposure_micro_sec: int):
        """Set exposure (internal, in microseconds)"""
        data = {"AeEnable": auto_exposure, "ExposureTime" : exposure_micro_sec}
        response = requests.patch(f"{self._base_url}/settings", json=data)
        if response.status_code != 200:
            raise Exception("Echec de la mise à jour des paramètres")
        
    def _get_fps_raw(self) -> float:
        """Get FPS (internal)"""
        settings = requests.get(f"{self._base_url}/settings").json()
        fps = 1000000.0/settings["FrameDurationLimits"][0]
        return fps
    
    def _set_fps_raw(self, fps: float):
        """Set FPS (internal)"""
        period_microsec = int(1000000.0/fps)
        data = {"FrameDurationLimits": [period_microsec, period_microsec]}
        response = requests.patch(f"{self._base_url}/settings", json=data)
        if response.status_code != 200:
            raise Exception("Echec de la mise à jour des paramètres")            
    
    def _set_id(self, id: str):
        """Set ID (internal)"""
        data = {"id": id}
        response = requests.patch(f"{self._base_url}/settings", json=data)
        if response.status_code != 200:
            raise Exception("Echec de la mise à jour des paramètres")            

