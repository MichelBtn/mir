from enum import Enum, auto
from pathlib import Path
import subprocess
from typing_extensions import override
from PySide6.QtCore import Signal
from mir_utils.ui.view_model_base import VMAction, ViewModelBase
from mir_utils.ui.dialogs import IDialogProvider
from mir_utils.concurrency import BackgroundWorker
from mir_devices.communication_ports import serial_get_available_ports
from mir_devices.esp_sensors import EspSensor, EspSensorSimulationConfiguration

# Chemin par défaut du firmware. Modifiable librement : le champ texte
# dans la vue permet de l'ajuster sans recompiler.
DEFAULT_FIRMWARE_PATH: Path = (
    Path(__file__).resolve().parent.parent
    / "esp32_sensor"
    / ".pio"
    / "build"
    / "esp32-wroom"
    / "firmware.bin"
)

# Clés normalisées de la configuration Wi-Fi. Le firmware peut renvoyer
# indifféremment majuscules ou minuscules (selon versions), on harmonise
# toujours vers les majuscules.
AP_KEYS: tuple[str, ...] = ("AP1_SSID", "AP1_PWD", "AP2_SSID", "AP2_PWD")


class DeployVMAction(Enum):
    FLASH = auto()
    READ_CFG = auto()
    WRITE_CFG = auto()
    REFRESH_PORTS = auto()


class DeployState(Enum):
    INIT = auto()        # aucun port sélectionné
    READY = auto()       # port sélectionné, idle
    BUSY = auto()        # une opération est en cours (esptool ou read/write)


class Esp32DeployViewModel(ViewModelBase[DeployVMAction]):

    ports_changed = Signal(list)              # list[str]
    status_changed = Signal(str)              # court message d'état
    config_loaded = Signal(dict)              # AP config lue depuis le capteur (clés normalisées)
    flash_finished = Signal(bool, str)        # success, output complet (stdout + stderr)
    state_changed = Signal(DeployState)
    busy_changed = Signal(bool)               # GUI disable indicator

    def __init__(self, dialogProvider: IDialogProvider):
        super().__init__(dialogProvider)
        self._selected_port: str = ""
        self._firmware_path: str = str(DEFAULT_FIRMWARE_PATH)
        self._available_ports: list[str] = []
        self._state: DeployState = DeployState.INIT
        self._worker = BackgroundWorker()

        # --- Actions exposées à la vue ---
        self._actions[DeployVMAction.FLASH] = VMAction(
            "Flasher le firmware", "Flash le firmware via esptool sur le port sélectionné"
        )
        self._actions[DeployVMAction.READ_CFG] = VMAction(
            "Lire la configuration Wi-Fi", "Lit la configuration des identifiants Wi-Fi depuis l'ESP32 sur le port série"
        )
        self._actions[DeployVMAction.WRITE_CFG] = VMAction(
            "Appliquer la configuration Wi-Fi", "Envoie la configuration des identifiants Wi-Fi à l'ESP32"
        )
        self._actions[DeployVMAction.REFRESH_PORTS] = VMAction(
            "Rafraîchir", "Recherche les ports série disponibles"
        )

        self._refresh_action_state()
        self._scan_ports()

    # ---------------------------------------------------------------- context
    @override
    def _enter_context(self):
        pass

    @override
    def _exit_context(self, exc_type, exc_value, traceback):
        self._worker.shutdown()

    # --------------------------------------------------------------- properties
    def get_available_ports(self) -> list[str]:
        return list(self._available_ports)

    def get_selected_port(self) -> str:
        return self._selected_port

    def get_default_firmware_path(self) -> str:
        return str(DEFAULT_FIRMWARE_PATH)

    # ---------------------------------------------------------------- selection
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
        self._set_state(DeployState.READY if self._selected_port else DeployState.INIT)

    def set_firmware_path(self, path: str):
        self._firmware_path = path or ""

    # ------------------------------------------------------------------ helpers
    def _create_serial_sensor(self) -> EspSensor:
        """
        Crée une instance EspSensor minimale pour dialoguer sur la liaison série.
        Seuls mir_connect_serial / read_ap_configuration / write_ap_configuration
        sont utilisés — l'adresse IP et le sensor_type passés dans la config sont
        ignorés dans ce mode série.
        """
        return EspSensor(
            "deploy",
            EspSensorSimulationConfiguration(sensor_type="esp_simulation", ip="0.0.0.0"),
        )

    def _normalize_ap_config(self, raw: dict[str, str] | None) -> dict[str, str]:
        """
        Retourne un dict avec exactement les 4 clés AP1_SSID/AP1_PWD/AP2_SSID/AP2_PWD
        en majuscules, indépendamment de ce que le firmware renvoie.
        """
        out: dict[str, str] = {k: "" for k in AP_KEYS}
        if not raw:
            return out
        for k, v in raw.items():
            key_upper = k.strip().upper()
            if key_upper in out:
                out[key_upper] = str(v)
        return out

    def _set_state(self, state: DeployState):
        self._state = state
        self.state_changed.emit(state)
        self._refresh_action_state()

    def _refresh_action_state(self):
        busy = self._state == DeployState.BUSY
        self.busy_changed.emit(busy)

        has_port = bool(self._selected_port)
        has_firmware = bool(self._firmware_path) and Path(self._firmware_path).is_file()

        self._actions[DeployVMAction.FLASH].set_enabled(
            (not busy) and has_port and has_firmware
        )
        self._actions[DeployVMAction.READ_CFG].set_enabled(
            (not busy) and has_port
        )
        self._actions[DeployVMAction.WRITE_CFG].set_enabled(
            (not busy) and has_port
        )
        self._actions[DeployVMAction.REFRESH_PORTS].set_enabled(not busy)

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

        # Capture locale : on évite de relire les attributs d'instance depuis
        # le thread worker (perdrait toute garantie de cohérence si le GUI
        # émettait un changement pendant l'appel).
        port = self._selected_port
        firmware = self._firmware_path

        self._set_state(DeployState.BUSY)
        self._worker.run(
            lambda: self._do_flash(port, firmware),
            self._on_flash_finished,
            self._on_flash_failed,
            guard_flag_owner=self,
            guard_flag="_flash_in_progress",
        )

    def _do_flash(self, port: str, firmware: str) -> tuple[bool, str, str]:
        cmd = [
            "esptool.py",
            "--chip", "esp32",
            "--port", port,
            "--baud", "115200",
            "write_flash",
            "0x1000", firmware,
        ]
        # capture_output=True : stdout/stderr collectés en mémoire.
        # Décodage manuel pour gérer les erreurs d'encodage (esptool émet
        # parfois des caractères ANSI / binaires non UTF-8).
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=False,
            timeout=300,
        )
        out = proc.stdout.decode("utf-8", errors="replace") if proc.stdout else ""
        err = proc.stderr.decode("utf-8", errors="replace") if proc.stderr else ""
        return (proc.returncode == 0, out, err)

    def _on_flash_finished(self, result: tuple[bool, str, str]):
        ok, out, err = result
        full = out + (("\n[stderr]\n" + err) if err else "")
        self.flash_finished.emit(ok, full)
        if ok:
            self.status_changed.emit("Flash terminé avec succès")
            self._dialogProvider.information(
                "Flash terminé", "Le firmware a été flashé avec succès."
            )
        else:
            self.status_changed.emit("Échec du flash (cf. log)")
            self._dialogProvider.error(
                "Échec du flash", "esptool a retourné un code d'erreur. Voir le log."
            )
        self._set_state(DeployState.READY if self._selected_port else DeployState.INIT)

    def _on_flash_failed(self, error: Exception):
        self.status_changed.emit(f"Erreur esptool : {error}")
        self._dialogProvider.exception(error)
        self._set_state(DeployState.READY if self._selected_port else DeployState.INIT)

    # ----------------------------------------------------------- ap config read
    def read_ap_configuration(self):
        if not self._selected_port:
            self._dialogProvider.warning("Port non sélectionné", "Veuillez choisir un port série.")
            return
        self._set_state(DeployState.BUSY)
        self._worker.run(
            self._do_read_ap_configuration,
            self._on_read_ap_finished,
            self._on_read_ap_failed,
            guard_flag_owner=self,
            guard_flag="_read_in_progress",
        )

    def _do_read_ap_configuration(self) -> dict[str, str] | None:
        sensor = self._create_serial_sensor()
        try:
            sensor.mir_connect_serial(self._selected_port)
            return sensor.read_ap_configuration()
        finally:
            try:
                sensor.mir_disconnect()
            except Exception:
                pass

    def _on_read_ap_finished(self, config: dict[str, str] | None):
        if not config:
            self.status_changed.emit("Lecture : aucune configuration reçue")
            self._dialogProvider.warning(
                "Lecture configuration",
                "L'ESP32 n'a pas renvoyé de configuration valide.",
            )
        else:
            normalized = self._normalize_ap_config(config)
            self.status_changed.emit("Configuration Wi-Fi lue depuis l'ESP32")
            self.config_loaded.emit(normalized)
            self._dialogProvider.information(
                "Lecture configuration",
                "Configuration Wi-Fi lue avec succès depuis l'ESP32.",
            )
        self._set_state(DeployState.READY if self._selected_port else DeployState.INIT)

    def _on_read_ap_failed(self, error: Exception):
        self.status_changed.emit(f"Erreur lecture : {error}")
        self._dialogProvider.exception(error)
        self._set_state(DeployState.READY if self._selected_port else DeployState.INIT)

    # ---------------------------------------------------------- ap config write
    def write_ap_configuration(self, config: dict[str, str]):
        if not self._selected_port:
            self._dialogProvider.warning("Port non sélectionné", "Veuillez choisir un port série.")
            return
        if not config:
            self._dialogProvider.warning(
                "Configuration vide",
                "Aucun identifiant Wi-Fi n'a été saisi ; rien à envoyer.",
            )
            return

        self._set_state(DeployState.BUSY)
        # Normalisation : on envoie toujours les clés en majuscules au firmware.
        payload = self._normalize_ap_config(config)
        self._worker.run(
            lambda: self._do_write_ap_configuration(payload),
            self._on_write_ap_finished,
            self._on_write_ap_failed,
            guard_flag_owner=self,
            guard_flag="_write_in_progress",
        )

    def _do_write_ap_configuration(self, payload: dict[str, str]) -> bool:
        sensor = self._create_serial_sensor()
        try:
            sensor.mir_connect_serial(self._selected_port)
            return sensor.write_ap_configuration(payload)
        finally:
            try:
                sensor.mir_disconnect()
            except Exception:
                pass

    def _on_write_ap_finished(self, success: bool):
        if success:
            self.status_changed.emit("Configuration Wi-Fi envoyée à l'ESP32")
            self._dialogProvider.information(
                "Envoi configuration",
                "Les identifiants Wi-Fi ont été écrits sur l'ESP32.",
            )
        else:
            self.status_changed.emit("Échec de l'écriture de la configuration Wi-Fi")
            self._dialogProvider.error(
                "Échec écriture",
                "L'ESP32 n'a pas confirmé l'écriture (status != success).",
            )
        self._set_state(DeployState.READY if self._selected_port else DeployState.INIT)

    def _on_write_ap_failed(self, error: Exception):
        self.status_changed.emit(f"Erreur écriture : {error}")
        self._dialogProvider.exception(error)
        self._set_state(DeployState.READY if self._selected_port else DeployState.INIT)
