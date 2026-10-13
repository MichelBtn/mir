import platform
from serial import Serial
import threading
import time
from queue import Queue
from PySide6.QtCore import QObject
import socket
from concurrent.futures import Future
import glob

def find_serial_ports_windows() -> list[str]:
    from serial.tools import list_ports  # Part of pyserial library
    # List COM ports using pyserial
    return [port.device for port in list_ports.comports()]

# --- macOS (Darwin) ---------------------------------------------------------
# Linux : /dev/ttyUSB* (ponts USB-UART), /dev/ttyACM* (CDC-ACM).
# macOS : pas de ttyUSB*/ttyACM*. Noms observés :
#   ponts USB-UART : /dev/cu.usbserial-*, /dev/tty.usbserial-*,
#                    *wchusbserial* (CH340/WCH), *SLAB_* (CP210x Silabs), *UART*
#   CDC-ACM        : /dev/cu.usbmodem*, /dev/tty.usbmodem*
#                    (ex. /dev/cu.usbmodem5b3d0492331)
_USB_UART_GLOBS_DARWIN = (
    "/dev/cu.usbserial*",
    "/dev/tty.usbserial*",
    "/dev/cu.wchusbserial*",
    "/dev/tty.wchusbserial*",
    "/dev/cu.SLAB*",
    "/dev/tty.SLAB*",
    "/dev/cu.UART*",
    "/dev/tty.UART*",
)
_ACM_GLOBS_DARWIN = (
    "/dev/cu.usbmodem*",
    "/dev/tty.usbmodem*",
)

def _glob_many(patterns: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    for pattern in patterns:
        found += glob.glob(pattern)
    return found


def _pyserial_darwin_matches(predicate) -> list[str]:
    """Complément pyserial sur macOS (glob seul peut rater un pilote)."""
    try:
        from serial.tools import list_ports
        devices = [port.device for port in list_ports.comports()]
    except Exception:
        return []
    return [d for d in devices
            if "bluetooth" not in d.lower() and predicate(d.lower())]


def _unique_sorted(ports: list[str]) -> list[str]:
    return sorted(set(ports), key=str.lower)

def find_usb_serial_ports():
    system = platform.system()
    #windows
    if system == "Windows":
        return find_serial_ports_windows()
    #macOS
    if system == "Darwin":
        # Ponts USB-UART + CDC-ACM (un ESP32-S2/S3 natif apparaît en usbmodem).
        candidates = _glob_many(_USB_UART_GLOBS_DARWIN + _ACM_GLOBS_DARWIN)
        candidates += _pyserial_darwin_matches(
            lambda d: ("usbserial" in d or "usbmodem" in d or "wchusbserial" in d
                       or "slab" in d or "uart" in d))
        return _unique_sorted(candidates)
    #linux
    return sorted(glob.glob("/dev/ttyUSB*"))

def find_acm_serial_ports():
    system = platform.system()
    #windows
    if system == "Windows":
        return find_serial_ports_windows()
    #macOS
    if system == "Darwin":
        candidates = _glob_many(_ACM_GLOBS_DARWIN)
        candidates += _pyserial_darwin_matches(lambda d: "usbmodem" in d)
        return _unique_sorted(candidates)
    #Linux        
    return sorted(glob.glob("/dev/ttyACM*"))

class CommPort(QObject):
    def __init__(self, end_of_line:str="\n", command_prefix="#", connect_timeout=5.0, command_timeout=1.0):
        self._end_of_line = end_of_line
        self._end_of_line_bytes = bytes(end_of_line, 'utf-8')
        self._connect_timeout = connect_timeout
        self._command_timeout = command_timeout
        self._command_prefix = command_prefix
        self._queue = Queue()
        self._thread = None
        self._stop = threading.Event()

    def _open(self):
        pass
    
    def _close(self):
        pass

    def open(self):
        self._open()
        self._stop.clear()
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    def close(self):
        self._stop.set()
        self._queue.put(None)  # débloquer le worker
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        self._close()

    def write_line(self, command: str):
        pass

    def read_line(self) -> str:
        return ""

    def _worker_loop(self):
        while not self._stop.is_set():
            item = self._queue.get()
            if item is None:  # signal d'arrêt
                break
            command, future = item
            try:
                result = self._execute_command(command)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)

    def _execute_command(self, command: str) -> str:
        self.write_line(command)
        return self.read_line()

    def send_command(self, command: str) -> str:
        """Bloquant — pour les appels ponctuels (connect, config...)"""
        #return self.submit_command(command).result(timeout=self._timeout + 0.5)
        return self._execute_command(command)
    
    def submit_command(self, command: str) -> Future:
        """Non bloquant — retourne un Future immédiatement"""
        if not self._thread or not self._thread.is_alive():
            raise ConnectionError("Non connecté")
        future = Future()
        self._queue.put((command, future))
        return future

#========= Serie ===========================================================
class SerialPort(CommPort):
    
    def __init__(self, port, baudrate=115200, end_of_line:str="\n", command_prefix="#", 
                 connect_timeout:float=5.0, command_timeout:float=1.0, enable_rts_dtr=True, empty_loop:bool=False):
        super().__init__(end_of_line, command_prefix=command_prefix, connect_timeout=connect_timeout, command_timeout=command_timeout)
        self.ser = Serial()
        self.ser.port = port
        self.ser.baudrate = baudrate
        self._enable_rts_dtr = enable_rts_dtr
        self._empty_loop = empty_loop
        
    # --- Ouverture / Fermeture ------------------------------------------------
    def _open(self):
        if self.ser.is_open:
            return
        self.ser.timeout = self._connect_timeout
        self.ser.dtr = self._enable_rts_dtr
        self.ser.rts = self._enable_rts_dtr
        self.ser.open()
        if self._empty_loop:        
            self.ser.timeout = 1.0
            start = time.time()
            quiet_time = 0
            while time.time() - start < 15.0:     # timeout de sécurité 10s
                time.sleep(0.1)
                if self.ser.in_waiting == 0:
                    quiet_time += 0.1
                    if quiet_time >= 1.0:        # 1s de silence → on considère que c’est fini
                        break
                else:
                    bytes = self.ser.read(self.ser.in_waiting)
                    str = bytes.decode('utf-8')
                    print(f"{str}", end="", flush=True)
                    quiet_time = 0
            time.sleep(0.1)
            self.ser.reset_input_buffer()
        self.ser.timeout = self._command_timeout
            
    def _close(self):
        if self.ser.is_open:
            self.ser.close()  # débloque read()

    # --- API utilisateur -------------------------------------------------------

    #génère une exception sur time out
    def read_line(self)->str:
        bytes = self.ser.read_until(self._end_of_line_bytes)
        str = bytes.decode('utf-8')
        str = str.strip()
        return str

    def write_line(self, command: str):
        command += self._end_of_line
        data = command.encode()
        self.ser.write(data)


#========= TCP ===========================================================
class TcpPort(CommPort):
    def __init__(self, host: str, port: int, end_of_line: str = "\n", command_prefix: str = "#", 
                 connect_timeout: float = 5.0, command_timeout: float = 0.25):
        super().__init__(end_of_line, command_prefix=command_prefix, connect_timeout=connect_timeout, command_timeout=command_timeout)
        self.host = host
        self.port = port
        self.sock = None

    def _open(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(self._connect_timeout)
        self.sock.connect((self.host, self.port))
        self.sock.settimeout(self._command_timeout)

    def _close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def write_line(self, command: str):
        if not self.sock:
            raise ConnectionError("Non connecté")
        message = command.strip() + self._end_of_line
        self.sock.sendall(message.encode("utf-8"))

    def read_line(self) -> str:
        if not self.sock:
            raise ConnectionError("Non connecté")
        data = b""
        while True:
            chunk = self.sock.recv(256)
            if not chunk:
                raise ConnectionError("Connexion fermée par le capteur")
            data += chunk
            if self._end_of_line_bytes in data:
                line, _, _ = data.partition(self._end_of_line_bytes)
                return line.decode("utf-8").strip()

if __name__ == '__main__':
    print("===== opening port...")
    #esp32-wroom enable_rts_dtr = True, empty_loop = False
    #esp32-cam enable_rts_dtr = False, empty_loop = True
    serial = SerialPort("/dev/ttyUSB0", baudrate=115200, enable_rts_dtr=False, empty_loop=True)
    serial.open()
    print("\r\n\r\n====== port opened, reading configuration")
    serial.write_line("get_configuration")
    line = serial.read_line()
    print(line)

