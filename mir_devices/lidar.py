import logging
import sys
import time
import codecs
import serial
import struct
import numpy as np
from numpy.typing import NDArray
from typing import Any

SYNC_BYTE = b'\xA5'
SYNC_BYTE2 = b'\x5A'

GET_INFO_BYTE  = b'\x50'
GET_HEALTH_BYTE = b'\x52'
STOP_BYTE      = b'\x25'
RESET_BYTE     = b'\x40'
SCAN_BYTE      = b'\x20'
MOTOR_CTRL_BYTE = b'\xA8'  # Commande correcte pour C1/S-series

DESCRIPTOR_LEN = 7
INFO_LEN   = 20
HEALTH_LEN = 3
INFO_TYPE   = 4
HEALTH_TYPE = 6
SCAN_TYPE   = 129   # 0x81
SCAN_SIZE   = 5

DEFAULT_MOTOR_RPM = 600   # RPM raisonnable pour le C1

_HEALTH_STATUSES = {0: 'Good', 1: 'Warning', 2: 'Error'}


class RPLidarException(Exception):
    pass


def _b2i(byte):
    return byte if int(sys.version[0]) == 3 else ord(byte)

def _showhex(signal):
    return [format(_b2i(b), '#04x') for b in signal]

class RPLidar:

    def __init__(self, port, baudrate=460800, timeout=3, logger=None):
        self._serial     = None
        self.port        = port
        self.baudrate    = baudrate
        self.timeout     = timeout
        self.scanning    = False
        self.motor_running = False

        if logger is None:
            logger = logging.getLogger('rplidar')
        self.logger = logger

    # ------------------------------------------------------------------ serial

    def connect(self):
        if self._serial is not None:
            self.disconnect()
        try:
            self._serial = serial.Serial(
                self.port, self.baudrate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout)
        except serial.SerialException as err:
            raise RPLidarException('Failed to connect: %s' % err)

    def disconnect(self):
        if self._serial is None:
            return
        self._serial.close()
        self._serial = None

    # ------------------------------------------------------------------ motor

    def start_motor(self, rpm=DEFAULT_MOTOR_RPM):
        """Démarre le moteur via MOTOR_SPEED_CTRL (0xA8) — commande C1/S-series."""
        self.logger.info('Starting motor at %d RPM', rpm)
        payload = struct.pack('<H', rpm)          # uint16 little-endian
        self._send_payload_cmd(MOTOR_CTRL_BYTE, payload)
        self.motor_running = True
        time.sleep(1.0)   # laisse le moteur atteindre sa vitesse de croisière

    def stop_motor(self):
        """Arrête le moteur (RPM = 0 → idle state selon le protocole)."""
        self.logger.info('Stopping motor')
        payload = struct.pack('<H', 0)
        self._send_payload_cmd(MOTOR_CTRL_BYTE, payload)
        self.motor_running = False

    # ------------------------------------------------------------------ low-level I/O

    def _send_cmd(self, cmd):
        req = SYNC_BYTE + cmd
        assert self._serial is not None, "_send_cmd : Serial port is not connected"
        self._serial.write(req)
        self.logger.debug('Command sent: %s', _showhex(req))

    def _send_payload_cmd(self, cmd, payload):
        assert self._serial is not None, "_send_payload_cmd : Serial port is not connected"
        size = struct.pack('B', len(payload))
        req  = SYNC_BYTE + cmd + size + payload
        checksum = 0
        for v in struct.unpack('B' * len(req), req):
            checksum ^= v
        req += struct.pack('B', checksum)
        self._serial.write(req)
        self.logger.debug('Command sent: %s', _showhex(req))

    def _read_descriptor(self):
        assert self._serial is not None, "_read_descriptor : Serial port is not connected"
        descriptor = self._serial.read(DESCRIPTOR_LEN)
        self.logger.debug('Descriptor: %s', _showhex(descriptor))

        if len(descriptor) != DESCRIPTOR_LEN:
            raise RPLidarException(
                'Descriptor length mismatch: got %d bytes instead of %d. '
                'Raw: %s' % (len(descriptor), DESCRIPTOR_LEN, _showhex(descriptor)))

        if not descriptor.startswith(SYNC_BYTE + SYNC_BYTE2):
            raise RPLidarException(
                'Incorrect descriptor start bytes: %s' % _showhex(descriptor))

        # Bytes [2..4] = Data Response Length (30 bits)
        # Byte [5]     = Send Mode (2 bits hauts) | length suite (6 bits bas)
        # Byte [6]     = Data Type
        data_len = (_b2i(descriptor[2])
                    | (_b2i(descriptor[3]) << 8)
                    | (_b2i(descriptor[4]) << 16)
                    | ((_b2i(descriptor[5]) & 0x3F) << 24))  # 30 bits
        send_mode = (_b2i(descriptor[5]) >> 6) & 0x03        # 2 bits hauts
        data_type = _b2i(descriptor[6])

        is_single = (send_mode == 0x00)
        return data_len, is_single, data_type

    def _read_scan_packet(self):
        assert self._serial is not None, "_read_scan_packet : Serial port is not connected"
        """Lit un paquet de scan de 5 bytes en se resynchronisant si nécessaire."""
        while True:
            # Lire le premier byte et vérifier que S != S̄
            raw = self._serial.read(1)
            if len(raw) == 0:
                raise RPLidarException('Timeout reading scan byte')
            
            b0 = _b2i(raw[0])
            s  = b0 & 0b1
            s_ = (b0 >> 1) & 0b1
            
            if s == s_:
                # Byte invalide, on avance d'un byte (resync)
                self.logger.debug('Resyncing scan stream...')
                continue
            
            # Premier byte valide, lire les 4 suivants
            rest = self._serial.read(4)
            if len(rest) < 4:
                raise RPLidarException('Timeout reading scan packet')
            
            raw = raw + rest
            
            # Vérifier le check bit
            if _b2i(raw[1]) & 0b1 != 1:
                self.logger.debug('Check bit invalid, resyncing...')
                continue
            
            # Paquet valide
            new_scan = bool(s)
            quality  = b0 >> 2
            angle    = ((_b2i(raw[1]) >> 1) + (_b2i(raw[2]) << 7)) / 64.0
            distance = (_b2i(raw[3]) + (_b2i(raw[4]) << 8)) / 4.0
            return new_scan, quality, angle, distance

    def _read_response(self, dsize):
        assert self._serial is not None, "_read_response : Serial port is not connected"
        self.logger.debug('Reading %d bytes...', dsize)
        deadline = time.time() + self.timeout
        while self._serial.inWaiting() < dsize:
            if time.time() > deadline:
                raise RPLidarException(
                    'Timeout waiting for %d bytes (got %d)'
                    % (dsize, self._serial.inWaiting()))
            time.sleep(0.001)
        return self._serial.read(dsize)

    # ------------------------------------------------------------------ public commands

    def get_info(self):
        assert self._serial is not None, "get_info : Serial port is not connected"
        self._serial.flushInput()
        self._send_cmd(GET_INFO_BYTE)
        dsize, is_single, dtype = self._read_descriptor()

        if dsize != INFO_LEN:
            raise RPLidarException('Wrong GET_INFO reply length: %d' % dsize)
        if not is_single:
            raise RPLidarException('Expected single response mode')
        if dtype != INFO_TYPE:
            raise RPLidarException('Wrong response data type: %d' % dtype)

        raw = self._read_response(dsize)
        return {
            'model':        _b2i(raw[0]),
            'firmware':     (_b2i(raw[2]), _b2i(raw[1])),   # (major, minor)
            'hardware':     _b2i(raw[3]),
            'serialnumber': codecs.decode(
                                codecs.encode(raw[4:], 'hex').upper(), 'ascii'),
        }

    def get_health(self):
        assert self._serial is not None, "get_health : Serial port is not connected"
        self._serial.flushInput()
        self._send_cmd(GET_HEALTH_BYTE)
        dsize, is_single, dtype = self._read_descriptor()

        if dsize != HEALTH_LEN:
            raise RPLidarException('Wrong GET_HEALTH reply length: %d' % dsize)
        if not is_single:
            raise RPLidarException('Expected single response mode')
        if dtype != HEALTH_TYPE:
            raise RPLidarException('Wrong response data type: %d' % dtype)

        raw = self._read_response(dsize)
        status     = _HEALTH_STATUSES[_b2i(raw[0])]
        # little-endian : LSB en raw[1], MSB en raw[2]
        error_code = _b2i(raw[1]) | (_b2i(raw[2]) << 8)
        return status, error_code

    def stop(self):
        assert self._serial is not None, "stop : Serial port is not connected"
        self._send_cmd(STOP_BYTE)
        time.sleep(0.05)
        self._serial.flushInput()
        self.scanning = False

    def _wait_for_boot(self, timeout=3.0):
        assert self._serial is not None, "_wait_for_boot : Serial port is not connected"
        """Attend que le capteur finisse d'envoyer sa bannière de boot."""
        self.logger.info('Waiting for boot banner to complete...')
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(0.1)
            # Si rien n'arrive pendant 200 ms, le boot est terminé
            if self._serial.inWaiting() == 0:
                time.sleep(0.2)
                if self._serial.inWaiting() == 0:
                    break
        # Vider tout ce que le capteur a envoyé pendant le boot
        boot_data = self._serial.read(self._serial.inWaiting())
        self.logger.info('Boot banner flushed (%d bytes): %s',
                        len(boot_data),
                        boot_data.decode('ascii', errors='replace').strip())
        
    def reset(self):
        assert self._serial is not None, "reset : Serial port is not connected"
        self._send_cmd(RESET_BYTE)
        time.sleep(2)       # le protocole exige ≥ 500 ms
        self._serial.flushInput()

    def start_scan(self):
        assert self._serial is not None, "start_scan : Serial port is not connected"
        status, error_code = self.get_health()
        self.logger.info('Health: %s [%d]', status, error_code)

        if status == 'Error':
            self.logger.warning('Sensor in error state, sending RESET...')
            self.reset()
            status, error_code = self.get_health()
            if status == 'Error':
                raise RPLidarException(
                    'Hardware failure, error code: %d' % error_code)

        self._send_cmd(SCAN_BYTE)
        dsize, is_single, dtype = self._read_descriptor()

        if dsize != SCAN_SIZE:
            raise RPLidarException('Wrong SCAN reply length: %d' % dsize)
        if is_single:
            raise RPLidarException('Expected multiple response mode')
        if dtype != SCAN_TYPE:
            raise RPLidarException('Wrong response data type: %d' % dtype)

        # Vider les premiers bytes potentiellement invalides
        # (le moteur n'est peut-être pas encore stable)
        time.sleep(0.1)
        self._serial.flushInput()  # ← flush APRÈS le descriptor, pas avant
        self.scanning = True

    # ------------------------------------------------------------------ iterators

    def iter_measures(self, max_buf_bytes=10000):
        if not self.motor_running:
            self.start_motor()
        if not self.scanning:
            self.start_scan()
        assert self._serial is not None, "iter_measures : Serial port is not connected"

        while True:
            if max_buf_bytes and self._serial.inWaiting() > max_buf_bytes:
                self.logger.warning('Buffer overflow (%d bytes), resetting scan...',
                                    self._serial.inWaiting())
                self.stop()
                self.start_scan()

            yield self._read_scan_packet()

    def iter_scans(self, max_buf_bytes=10000, min_len=5):
        scan_list = []
        for new_scan, quality, angle, distance in self.iter_measures(max_buf_bytes):
            if new_scan:
                if len(scan_list) >= min_len:
                    yield scan_list
                scan_list = []
            if distance > 0:
                scan_list.append((quality, angle, distance))

    def get_last_scan(self):
        """Retourne la dernière trame complète (un tour de 360°).
        
        Attend deux fronts montants S=1 consécutifs pour garantir
        qu'on retourne une trame entière.
        
        Returns
        -------
        scan : list of tuples (quality, angle, distance)
        """
        if not self.motor_running:
            self.start_motor()
        if not self.scanning:
            self.start_scan()

        # Attendre le début d'une nouvelle trame (S=1)
        while True:
            new_scan, quality, angle, distance = self._read_scan_packet()
            if new_scan:
                break

        # Enregistrer les mesures jusqu'au prochain S=1
        scan = []
        if distance > 0:
            scan.append((quality, angle, distance))

        while True:
            new_scan, quality, angle, distance = self._read_scan_packet()
            if new_scan:
                break
            if distance > 0:
                scan.append((quality, angle, distance))

        return scan

class LidarSensor():
    def __init__(self, port:str):
        self._rplidar = None
        self._port = port
        self._is_connected = False

    def connect(self, async_read: bool = False) -> None:
        self._rplidar = RPLidar(self._port, baudrate=460800, timeout=3)
        self._rplidar.connect()
        self._rplidar.reset()
        status, error_code = self._rplidar.get_health()
        if status == 'Error':
            raise RPLidarException('Le Lidar est en erreur après reset : %d' % error_code)        
        self._rplidar.start_motor()
        self._rplidar.start_scan()
        self._is_connected = True
        if async_read:
            self.start_background_scan()

    def disconnect(self) -> None:
        self._is_connected = False
        if hasattr(self, '_bg_running'):
            self._bg_running = False
            self._bg_thread.join(timeout=2.0)    
        if self._rplidar is not None:               
            self._rplidar.stop()
            self._rplidar.stop_motor()
            self._rplidar.disconnect()
            self._rplidar = None

    def is_connected(self) -> bool:
        return self._is_connected

    @staticmethod
    def scan_to_array(scan: list, n_sectors: int =360, aggregation: str ='mean') -> NDArray[Any]:
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
            result[:, 1] : distances en mm (0 si aucune mesure)
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

    def read(self, aggregation: str = 'mean') -> NDArray[Any]:
        if hasattr(self, '_scan_lock'):
            with self._scan_lock:
                if not self._last_scan:
                    raise RPLidarException('Pas de scan disponible!')
                return self.scan_to_array(self._last_scan, aggregation=aggregation)
        # Fallback sur la version synchrone si pas de thread
        assert self._rplidar is not None, "RPLidar is not connected"
        scan = self._rplidar.get_last_scan()
        return self.scan_to_array(scan)

    def start_background_scan(self):
        import threading
        self._last_scan = []
        self._scan_lock = threading.Lock()
        self._bg_running = True
        assert self._rplidar is not None, "RPLidar is not connected"

        def _worker():
            for scan in self._rplidar.iter_scans():
                if not self._bg_running:
                    break
                with self._scan_lock:
                    self._last_scan = scan

        self._bg_thread = threading.Thread(target=_worker, daemon=True)
        self._bg_thread.start()
    
    def iter_scans_to_array(self, max_buf_bytes: int = 10000,
                                min_len: int = 5,
                                aggregation: str = 'mean'):
        if not self._is_connected:
            raise RPLidarException('Lidar non connecté')
        assert self._rplidar is not None, "RPLidar is not connected"            
        for scan in self._rplidar.iter_scans(max_buf_bytes, min_len):
            yield self.scan_to_array(scan, aggregation=aggregation)