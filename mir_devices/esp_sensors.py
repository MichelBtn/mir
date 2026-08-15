from threading import Lock
import socket
import struct
import time
from concurrent.futures import Future
from loguru import logger
from typing import Any, cast
import numpy as np
import matplotlib.pyplot as plt
from mir_devices.communication_ports import TcpPort, SerialPort
from mir_devices.mir_sensor import (EspSensorConfiguration, 
                                    EspSensorLidarConfiguration, 
                                    EspSensorSimulationConfiguration, 
                                    SensorProperty,
                                    mirSensor,
                                    EspSensorWheatherConfiguration)
from mir_devices.mir_device import (ObservablePropertyPolar, 
                                    ObservableProperty, 
                                    ObservablePropertyFloat, 
                                    ObservationValue,
                                    ActionValue,
                                    device_feature_name_from_feature)
from mir_utils.concurrency import BackgroundWorker

class EspSensor(mirSensor):
    HEADER_SIZE = 16
    MAGIC = b'\xA5\x5A'

    def __init__(self, sensor_key:str, cfg:EspSensorConfiguration):
        super().__init__(sensor_key)
        self._data : dict[str, ObservationValue] | None = None
        self._ip_address = cfg.ip
        self._tcp_cmd_port = 5000
        self._tcp_data_port = 5001
        self._tcpCommPort = TcpPort(self._ip_address, self._tcp_cmd_port, connect_timeout=2.0, command_timeout=0.25)
        self._commPort = None
        self._info = ""
        self._future_command : Future|None = None
        self._is_connected = False
        self._values_names : list[str]|None = None
        self._worker = BackgroundWorker()
        self._data_locker = Lock()
        self._disconnect_forced_stop_loop = False
        self._data_socket:socket.socket|None = None
    
    def send_action(self, actions:dict[str, ActionValue])->dict[str, ActionValue]:
        return {}

    def test_connection(self) -> bool :
        if self._is_connected:
            raise RuntimeError("reset_sensor : le capteur est en cours d'utilisation")
        else:
            try:
                self._commPort = TcpPort(self._ip_address, self._tcp_cmd_port, connect_timeout=1.0, command_timeout=0.25)
                self._commPort.open()
                self.read_configuration()
                return True
            except Exception:
                return False
            finally:
                if self._commPort is not None:
                    self._commPort.close()
                    self._commPort = None
        
    def reset_sensor(self):
        if self._is_connected:
            raise RuntimeError("reset_sensor : le capteur est en cours d'utilisation")
        else:
            self._commPort = TcpPort(self._ip_address, self._tcp_cmd_port, connect_timeout=2.0, command_timeout=0.25)
            self._commPort.open()
            self._send_command("reboot")
            if self._commPort is not None:
                self._commPort.close()
                self._commPort = None

    """
    TODO: si besoin pour connexion sur le port série
    def set_conf(self, conf:object):
        self._conf = conf
    """
    def mir_connect(self)->None:
        """
        TODO: si besoin pour connexion sur le port série
        if self._conf is not None:
            self._commPort = SerialPort(self._conf, 115200)
        else:
            self._commPort = self._tcpCommPort
        """            
        self._commPort = self._tcpCommPort
        self._commPort.open()
        self._data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._data_socket.connect((self._ip_address, self._tcp_data_port))
        self._worker.run(self._loop, self._on_loop_finished, self._on_loop_failed, self)
        self._is_connected = True

    def mir_connect_serial(self, port:str, baudrate:int=115200, enable_rts_dtr: bool = False, empty_loop: bool = False):
        self._commPort = SerialPort(port, baudrate, enable_rts_dtr=enable_rts_dtr, empty_loop=empty_loop)
        self._commPort.open()
        self._is_connected = True

    def read_exactly(self, n):
        buf = b''
        if self._data_socket is None:
            raise RuntimeError("socket de données non initialisé")
        while len(buf) < n:
            chunk = self._data_socket.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("connexion fermée")
            buf += chunk
        return buf
    
    def _on_loop_failed(self, error:Exception):
        logger.error(f"thread de lecture terminé sur erreur : {error!r}")

    def _on_loop_finished(self, result:None):
        pass
    
    def _raw_data_size(self, count: int) -> int:
        return 0

    def _parse_data(self, data: bytes, count: int, timestamp: float) -> None:
        pass
    
    def get_observables(self) -> dict[str, ObservableProperty]:
        return {}

    def _loop(self) -> None:
        self._disconnect_forced_stop_loop = False
        while True:
            try:
                header = self.read_exactly(EspSensor.HEADER_SIZE)
                if header[:2] != EspSensor.MAGIC:
                    self._resync()
                    continue
                seq, ts, count = struct.unpack_from('<IQH', header, 2)
                raw_data = self.read_exactly(self._raw_data_size(count))
                self._parse_data(raw_data, count, ts / 1000000.0)
            except (ConnectionError, OSError) as e:
                if self._disconnect_forced_stop_loop:
                    logger.info("connexion fermée par l'utilisateur")
                else:                    
                    logger.error(f"connexion perdue : {e}")
                break
            except Exception as e:
                # Ne jamais laisser une erreur de parsing tuer le thread silencieusement
                logger.error(f"erreur de parsing, resync : {e}")
                self._resync()

    def _resync(self):
        """Avance octet par octet jusqu'à retrouver le magic."""
        buf = b''
        if self._data_socket is None:
            raise RuntimeError("socket de données non initialisé")
        while True:
            b = self._data_socket.recv(1)
            if not b:
                raise ConnectionError("connexion fermée pendant resync")
            buf = (buf + b)[-2:]
            if buf == EspSensor.MAGIC:
                return

    def mir_disconnect(self):
        self._disconnect_forced_stop_loop = True
        if self._data_socket is not None:
            try:
                self._data_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._data_socket.close()  # débloque read_exactly()
        self._is_connected = False
        if self._commPort is not None:
            self._commPort.close()
            self._commPort = None

    def mir_is_connected(self):
        return self._is_connected

    def _response_to_data(self, s: str) -> list[float]:
        result = [float(item) for item in s.split(';')]    
        result[0] /= 1000000.0 #timestamp en µs
        return result

    def _response_to_dict(self, s: str) -> dict[str, str]:
        result = {}
        for pair in s.split(';'):
            key, value = pair.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"')
            result[key] = value
        return result
    
    def _dict_to_str(self, d: dict) -> str:
        def fmt(v):
            return f'{v}' if isinstance(v, str) else str(v)
        return ';'.join(f'{k}={fmt(v)}' for k, v in d.items())

    def _send_command(self, command_and_args: str):
        if self._commPort is None:
            raise RuntimeError("Communication port is not initialized")
        self._command = command_and_args.split(' ', 1)[0]
        try:
            response = self._commPort.send_command(command_and_args)
            if response.startswith(f"#{self._command}"):
                return response.split(' ', 1)[1]
            logger.error(f"{self._command}, réponse inattendue : {response}")
        except Exception as e:
            logger.error(f"échec commande {command_and_args} : {e})")
        return None

    def read_ap_configuration(self) -> dict[str, str] | None:
        if not isinstance(self._commPort, SerialPort):
            raise RuntimeError("Seul le port série est autorisé pour la configuration des identifiants de point d'accès")
        response = self._send_command("get_ap_configuration")
        if response is None:
            return None
        return self._response_to_dict(response)
    
    def write_ap_configuration(self, configuration: dict) -> bool:
        str = self._dict_to_str(configuration) + ";"
        response = self._send_command(f"set_ap_configuration {str}")    
        if response != "status=success":
            logger.warning(f"write_ap_configuration({configuration}) a retourné une erreur  : {response}")
        return response == "status=success"

    def read_configuration(self) -> dict[str, str] | None:
        response = self._send_command("get_configuration")
        if response is None:
            return None
        return self._response_to_dict(response)

    def get_data(self):
        with self._data_locker:
            return self._data

    def write_configuration(self, configuration: dict) -> bool:
        str = self._dict_to_str(configuration) + ";"
        response = self._send_command(f"set_configuration {str}")    
        if response != "status=success":
            logger.warning(f"write_configuration({configuration}) a retourné une erreur  : {response}")
        return response == "status=success"

    def get_configurable_properties(self) -> dict[str, SensorProperty]:
        """Retourne les propriétés configurables (à surcharger si configurable)
        "sensor_type=%s;sensor_id=%s;ap1_ssid=%s;ap1_pwd=%s;ap1_ip=%s;ap2_ssid=%s;ap2_pwd=%s;ap2_ip=%s;wifi_timeout=%d;loop_period=%d",
        sensor_type, sensor_id, ap1_ssid, ap1_pwd, ap1_ip, ap2_ssid, ap2_pwd, ap2_ip, wifi_timeout, loop_period);
        """
        try:
            config = self.read_configuration()
            if config is None:
                return {}
            sensor_type = config["sensor_type"]
            ap1_ip = config["ap1_ip"]
            ap2_ip = config["ap2_ip"]
            wifi_timeout = config["wifi_timeout"]
            loop_period = config["loop_period"]
            current_ip = config["current_ip"]

            return {
                "sensor_type" : SensorProperty(
                    label="Type de capteur",
                    property_type="list",
                    current_value=sensor_type,
                    options=[
                        EspSensorLidarConfiguration.SENSOR_TYPE, 
                        EspSensorWheatherConfiguration.SENSOR_TYPE, 
                        EspSensorSimulationConfiguration.SENSOR_TYPE
                    ],
                    requires_reboot=True, 
                ),
                "current_ip":SensorProperty(
                    label="Adresse IP",
                    tooltip="Adresse IP courante",
                    property_type="str",
                    current_value=current_ip,
                    read_only=True
                ),
                "ap1_ip" : SensorProperty(
                    label="AP1 IP",
                    tooltip="adresse IP sur le point d'accès préféré (auto = adresse fournie par le point d'accès)",
                    property_type="str",
                    current_value=ap1_ip,
                    requires_reboot=True
                ),
                "ap2_ip" : SensorProperty(
                    label="AP2 IP",
                    tooltip="adresse IP sur le point d'accès secondaire (auto = adresse fournie par le point d'accès)",
                    property_type="str",
                    current_value=ap2_ip,
                    requires_reboot=True
                ),
                "wifi_timeout" : SensorProperty(
                    label="Wifi timeout",
                    tooltip="timeout pour la connexion wifi : connexion point d'accès préféré, si timeout bascule sur point d'accès secondaire",
                    property_type="int",
                    current_value=wifi_timeout,
                    requires_reboot=True
                ),
                "loop_period" : SensorProperty(
                    label="Loop period",
                    tooltip="période de boucle du capteur en ms",
                    property_type="int",
                    current_value=loop_period,  
                )    
            }
            
        except Exception as e:
            logger.error(f"Failed to get configurable properties: {e}")
            return {}        
    
    def set_property(self, key: str, value: Any) -> bool:
        return self.write_configuration({key:value})

    def get_observation(self) -> dict[str, ObservationValue]:
        observation = {}
        if len(self.subscribed_observations) > 0:
            data = self.get_data()
            if data is not None:
                for feature in self.subscribed_observations:
                    dev,feature_name = device_feature_name_from_feature(feature)
                    observation[feature] = data[feature_name]
        return observation


class EspSensorLidar(EspSensor):
    def _raw_data_size(self, count: int) -> int:
        return count * 5

    @staticmethod
    def scan_to_array(scan: list, n_sectors: int=500, aggregation: str ='mean') -> np.ndarray:
        """Convertit un scan en tableau numpy de taille fixe.
        
        Parameters
        ----------
        scan : list of tuples (quality, angle, distance)
        n_sectors : int
            Nombre de secteurs angulaires.
        aggregation : str
            Méthode d'agrégation quand plusieurs mesures tombent dans le même secteur :
            - 'mean'    : moyenne        → usage général
            - 'min'     : minimum        → détection d'obstacles (objet le plus proche)
            - 'max'     : maximum        → cartographie (objet le plus loin)
            - 'quality' : pondéré par la qualité du signal → meilleure mesure physique
        
        Returns
        -------
        result : np.ndarray of shape (n_sectors, 2)
            result[:, 0] : angles en degrés [0, 360)
            result[:, 1] : distances en cm (0 si aucune mesure)
        """
        angles    = np.linspace(0, 360, n_sectors, endpoint=False, dtype=np.float32)
        distances = np.zeros(n_sectors, dtype=np.float32)
        qualities = np.zeros(n_sectors, dtype=np.float32)
        counts    = np.zeros(n_sectors, dtype=np.int32)

        if aggregation == 'min':
            distances[:] = np.inf

        for quality, angle, distance in scan:
            idx = int(angle / 360.0 * n_sectors) % n_sectors

            if aggregation == 'mean':
                distances[idx] += distance
                qualities[idx] += quality
                counts[idx]    += 1

            elif aggregation == 'min':
                if distance < distances[idx]:
                    distances[idx] = distance
                    qualities[idx] = quality

            elif aggregation == 'max':
                if distance > distances[idx]:
                    distances[idx] = distance
                    qualities[idx] = quality

            elif aggregation == 'quality':
                distances[idx] += distance * quality
                qualities[idx] += quality
                counts[idx]    += 1

        # Finalisation
        if aggregation == 'mean':
            mask = counts > 0
            distances[mask] /= counts[mask]

        elif aggregation == 'quality':
            mask = qualities > 0
            distances[mask] /= qualities[mask]

        elif aggregation == 'min':
            distances[distances == np.inf] = 0.0

        return np.stack([angles, distances], axis=1)

    def _parse_data(self, data: bytes, count: int, timestamp: float) -> None:
        # Parser les points
        points = []
        for i in range(count):
            quality, angle, distance = struct.unpack_from('<BHH', data, i * 5)
            points.append((quality, angle / 10.0, distance))  # angle en degrés, dist en cm
        scan = self.scan_to_array(points, 400)
        with self._data_locker:
            self._data = {"": scan.copy()}

    def get_observables(self) -> dict[str, ObservableProperty]:
        return {self.sensor_key: ObservablePropertyPolar(400, 600)}

class EspSensorSimulation(EspSensor):
    def _raw_data_size(self, count: int) -> int:
        return count * 4

    def _parse_data(self, data: bytes, count: int, timestamp: float) -> None:
        (omega, theta) = struct.unpack_from('<ff', data, 0)
        with self._data_locker:
            self._data = {'omega': omega, 'theta': theta, 'timestamp': timestamp}

    def get_observables(self) -> dict[str, ObservableProperty]:
        return { f"{self.sensor_key}.omega": ObservablePropertyFloat(-1, 1, "rad/s"), 
                 f"{self.sensor_key}.theta": ObservablePropertyFloat(-1, 1, "rad")}

class EspSensorWheather(EspSensor):
    def _raw_data_size(self, count: int) -> int:
        return count*4

    def _parse_data(self, data: bytes, count: int, timestamp: float) -> None:
        (temperature, rel_humidity) = struct.unpack_from('<ff', data, 0)
        with self._data_locker:
            self._data = {
                "temperature": temperature,
                "rel_humidity": rel_humidity
            }

    def get_observables(self) -> dict[str, ObservableProperty]:
        return { f"{self.sensor_key}.temperature": ObservablePropertyFloat(-10, 50, "°C"), 
                 f"{self.sensor_key}.rel_humidity": ObservablePropertyFloat(0, 100, "%")}
    

def simulation_test():
    sensor = EspSensorSimulation("sim1", EspSensorSimulationConfiguration(
        sensor_type="esp_simulation",
        ip="192.168.1.18"
    ))

    sensor.mir_connect()
    t0 = time.time()
    omega : list[float]= []
    theta : list[float]= []
    timestamps: list[float] = []
    print("Acquisition des données en cours, patentez... ")
    while time.time() - t0 < 2.5:
        time.sleep(0.025)
        data = sensor.get_data()
        if data is not None:
            omega.append(float(data["omega"]))
            theta.append(float(data["theta"]))
            timestamps.append(float(data["timestamp"]))
    sensor.mir_disconnect()

    t0 = timestamps[0]
    timestamps = [t - t0 for t in timestamps]
    plt.figure(figsize=(6, 4))
    plt.plot(timestamps, omega, label="Omega (rad/s)")
    plt.plot(timestamps, theta, label="Theta (rad)")
    plt.xlabel("Temps (s)")
    plt.ylabel("Valeurs")
    plt.title("Données Omega et Theta")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()

def lidar_test():
    sensor = EspSensorLidar("lidar", EspSensorLidarConfiguration(
        sensor_type="esp_lidar",
        ip="192.168.1.26"
    ))
    sensor.mir_connect()
    plt.ion()
    fig, raw_ax = plt.subplots(subplot_kw={'projection': 'polar'}, figsize=(6, 6))
    ax = cast(plt.PolarAxes, raw_ax)
    sc = ax.scatter([], [], s=2, alpha=0.8)
    ax.set_title('RPLIDAR C1 — Simulation Dynamique', va='bottom', pad=20)
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 600)
    try:
        while True:
            data = sensor.get_data()
            if data is None:
                continue
            scan_data = data[""]
            if isinstance(scan_data, np.ndarray):
                angles_rad = np.deg2rad(scan_data[:, 0])
                distances = scan_data[:, 1]
                sc.set_offsets(np.c_[angles_rad, distances])
            else:
                sc.set_offsets(np.c_[[], []])
            fig.canvas.draw()
            fig.canvas.flush_events()
            plt.pause(0.05)
    except KeyboardInterrupt:
        print("Simulation stoppée.")
    finally:
        sensor.mir_disconnect()

if __name__ == '__main__':
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    #simulation_test()
    lidar_test()
