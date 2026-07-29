from enum import Enum, auto
from pathlib import Path
import subprocess
from typing_extensions import override
from PySide6.QtCore import Signal
import re
import os
import subprocess
from PySide6.QtCore import Signal, QObject
from mir_utils.ui.view_model_base import VMAction, ViewModelBase
from mir_utils.ui.dialogs import IDialogProvider
from mir_utils.concurrency import BackgroundWorker
from mir_devices.communication_ports import serial_get_available_ports
from mir_devices.esp_sensors import EspSensor, EspSensorSimulationConfiguration

# Chemin par défaut du firmware.
DEFAULT_FIRMWARE_PATH: Path = (
    Path(__file__).resolve().parent.parent
    / "esp32_sensor"
    / ".pio"
    / "build"
    / "esp32dev"
    / "firmware.bin"
)

AP_KEYS: tuple[str, ...] = ("ap1_ssid", "ap1_pwd", "ap2_ssid", "ap2_ssid")


class DeployVMAction(Enum):
    FLASH = auto()
    READ_CFG = auto()
    WRITE_CFG = auto()
    REFRESH_PORTS = auto()


class Esp32DeployViewModel(ViewModelBase[DeployVMAction]):

    ports_changed = Signal(list)               # list[str]
    status_changed = Signal(str)               # message d'état
    config_loaded = Signal(dict)               # configuration AP lue
    flash_output_received = Signal(str)         # sortie de esptool
    busy_changed = Signal(bool)                # état occupé

    def __init__(self, dialogProvider: IDialogProvider):
        super().__init__(dialogProvider)
        self._selected_port: str = ""
        self._firmware_path: str = str(DEFAULT_FIRMWARE_PATH)
        self._available_ports: list[str] = []
        self._busy: bool = False
        self._worker = BackgroundWorker()

        # Actions exposées à la vue
        self._actions[DeployVMAction.FLASH] = VMAction(
            "Flasher le firmware",
            "Flash le firmware via esptool sur le port sélectionné",
        )
        self._actions[DeployVMAction.READ_CFG] = VMAction(
            "Lire la configuration Wi-Fi",
            "Lit la configuration des identifiants Wi-Fi depuis l'ESP32",
        )
        self._actions[DeployVMAction.WRITE_CFG] = VMAction(
            "Appliquer la configuration Wi-Fi",
            "Envoie la configuration des identifiants Wi-Fi à l'ESP32",
        )
        self._actions[DeployVMAction.REFRESH_PORTS] = VMAction(
            "Rafraîchir les ports",
            "Recherche les ports série disponibles",
        )

        self._refresh_action_state()
        self._scan_ports()

    @override
    def _enter_context(self):
        pass

    @override
    def _exit_context(self, exc_type, exc_value, traceback):
        self._worker.shutdown()

    # --------------------------------------------------------------- propriétés
    def get_available_ports(self) -> list[str]:
        return list(self._available_ports)

    def get_selected_port(self) -> str:
        return self._selected_port

    def get_default_firmware_path(self) -> str:
        return str(DEFAULT_FIRMWARE_PATH)

    # ---------------------------------------------------------------- ports série
    def scan_ports(self) -> list[str]:
        self._scan_ports()
        return self.get_available_ports()

    def _scan_ports(self):
        try:
            self._available_ports = serial_get_available_ports()
        except Exception:
            self._available_ports = []
        self.ports_changed.emit(self._available_ports)

    def set_selected_port(self, port: str):
        self._selected_port = port or ""
        self._refresh_action_state()

    def set_firmware_path(self, path: str):
        self._firmware_path = path or ""
        self._refresh_action_state()

    # ---------------------------------------------------------- helpers EspSensor
    def _create_serial_sensor(self) -> EspSensor:
        return EspSensor(
            "deploy",
            EspSensorSimulationConfiguration(sensor_type="esp_simulation", ip="0.0.0.0"),
        )

    # def _normalize_ap_config(self, raw: dict[str, str] | None) -> dict[str, str]:
    #     out: dict[str, str] = {k: "" for k in AP_KEYS}
    #     if not raw:
    #         return out
    #     for k, v in raw.items():
    #         key_upper = k.strip().upper()
    #         if key_upper in out:
    #             out[key_upper] = str(v)
    #     return out

    # ------------------------------------------------------------ rafraîchir états
    def _set_busy(self, busy: bool):
        self._busy = busy
        self.busy_changed.emit(busy)
        self._refresh_action_state()

    def _refresh_action_state(self):
        has_port = bool(self._selected_port)
        has_firmware = bool(self._firmware_path) and Path(self._firmware_path).is_file()

        self._actions[DeployVMAction.FLASH].set_enabled(
            (not self._busy) and has_port and has_firmware
        )
        self._actions[DeployVMAction.READ_CFG].set_enabled(
            (not self._busy) and has_port
        )
        self._actions[DeployVMAction.WRITE_CFG].set_enabled(
            (not self._busy) and has_port
        )
        self._actions[DeployVMAction.REFRESH_PORTS].set_enabled(not self._busy)

    # ------------------------------------------------------------------- flash
    def flash_firmware(self):
        if not self._selected_port:
            self._dialogProvider.warning("Port non sélectionné", "Veuillez choisir un port série.")
            return
        if not self._firmware_path:
            self._dialogProvider.warning("Firmware", "Veuillez spécifier un chemin de firmware.")
            return
        if not Path(self._firmware_path).is_file():
            self._dialogProvider.error(
                "Firmware introuvable",
                f"Le fichier firmware n'a pas été trouvé :\n{self._firmware_path}",
            )
            return

        port = self._selected_port
        firmware = self._firmware_path

        self._set_busy(True)
        self.status_changed.emit("Flash en cours...")
        self._worker.run(
            lambda: self._do_flash(port, firmware),
            self._on_flash_finished,
            self._on_flash_failed,
            guard_flag_owner=self,
            guard_flag="_flash_in_progress",
        )

    
    def build_flash_command(self, bin_dir: str, port: str) -> list[str]:
        return [
            "esptool.py", "--chip", "esp32", "--port", port, "--baud", "921600",
            "--before", "default_reset", "--after", "hard_reset",
            "write_flash", "-z", "--flash_mode", "dio", "--flash_freq", "40m", "--flash_size", "4MB",
            "0x1000",  os.path.join(bin_dir, "bootloader.bin"),
            "0x8000",  os.path.join(bin_dir, "partitions.bin"),
            "0xe000",  os.path.join(bin_dir, "boot_app0.bin"),
            "0x10000", os.path.join(bin_dir, "firmware.bin"),
        ]

    def _do_flash(self, port: str, firmware: str) -> int:
        ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
        def clean_line(line: str) -> str:
            return ANSI_ESCAPE.sub('', line).strip()

        bin_dir = Path("__file__").parent / "bin"
        cmd = self.build_flash_command(str(bin_dir), port)
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        pattern = re.compile(r"\((\d+)\s*%\)")
        if process is None or process.stdout is None:
            return -1
        for line in process.stdout:
            cleaned = clean_line(line)
            if cleaned:  # évite d'émettre des lignes vides après nettoyage
                self.flash_output_received.emit(cleaned)
            # self.log_line.emit(line.strip())
            # match = pattern.search(line)
            # if match:
            #     self.flash_output_received.emit(int(match.group(1)))
        process.wait()
        return process.returncode

        # return full_output

    def _on_flash_finished(self, output: int):
        self.flash_output_received.emit(output)
        message = "Le firmware a été flashé avec succès" if output == 0 else f"Le processus a retourné une erreur : {output}"
        self.status_changed.emit(message)
        self._dialogProvider.information("Flash terminé", message)
        self._set_busy(False)

    def _on_flash_failed(self, error: Exception):
        msg = str(error)
        self.flash_output_received.emit(msg)
        self.status_changed.emit("Échec du flash")
        self._dialogProvider.error("Échec du flash", f"Erreur : {error}")
        self._set_busy(False)

    # ---------------------------------------------------------- lecture config AP
    def read_ap_configuration(self):
        if not self._selected_port:
            self._dialogProvider.warning("Port non sélectionné", "Veuillez choisir un port série.")
            return

        self._set_busy(True)
        self.status_changed.emit("Lecture de la configuration Wi-Fi...")
        try:
            sensor = self._create_serial_sensor()
            sensor.mir_connect_serial(self._selected_port)
            try:
                config = sensor.read_ap_configuration()
            finally:
                sensor.mir_disconnect()

            if not config:
                self.status_changed.emit("Lecture : aucune configuration reçue")
                self._dialogProvider.warning("Lecture configuration", "L'ESP32 n'a pas renvoyé de configuration valide.")
            else:
                #normalized = self._normalize_ap_config(config)
                normalized = config
                self.status_changed.emit("Configuration Wi-Fi lue depuis l'ESP32")
                self.config_loaded.emit(normalized)
                self._dialogProvider.information("Lecture configuration", "Configuration Wi-Fi lue avec succès.")
        except Exception as e:
            self.status_changed.emit(f"Erreur lecture : {e}")
            self._dialogProvider.exception(e)
        finally:
            self._set_busy(False)

    # ---------------------------------------------------------- écriture config AP
    def write_ap_configuration(self, config: dict[str, str]):
        if not self._selected_port:
            self._dialogProvider.warning("Port non sélectionné", "Veuillez choisir un port série.")
            return
        if not config:
            self._dialogProvider.warning("Configuration vide", "Aucun identifiant Wi-Fi n'a été saisi.")
            return

        self._set_busy(True)
        self.status_changed.emit("Envoi de la configuration Wi-Fi...")

        #payload = self._normalize_ap_config(config)
        payload = config
        try:
            sensor = self._create_serial_sensor()
            sensor.mir_connect_serial(self._selected_port)
            try:
                success = sensor.write_ap_configuration(payload)
            finally:
                sensor.mir_disconnect()

            if success:
                self.status_changed.emit("Configuration Wi-Fi envoyée à l'ESP32")
                self._dialogProvider.information("Envoi configuration", "Les identifiants Wi-Fi ont été écrits sur l'ESP32.")
            else:
                self.status_changed.emit("Échec de l'écriture de la configuration Wi-Fi")
                self._dialogProvider.error("Échec écriture", "L'ESP32 n'a pas confirmé l'écriture.")
        except Exception as e:
            self.status_changed.emit(f"Erreur écriture : {e}")
            self._dialogProvider.exception(e)
        finally:
            self._set_busy(False)
