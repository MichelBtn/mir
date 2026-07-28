from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from mir_utils.ui.view_base import ViewBase
from mir_utils.ui.widgets import MainWindowBase
from mir_esp_deploy.esp32_deploy_view_model import (
    DeployState,
    DeployVMAction,
    Esp32DeployViewModel,
)


class Esp32DeployView(MainWindowBase, ViewBase[Esp32DeployViewModel, DeployVMAction]):
    """
    Vue principale du déployeur ESP32.

    Layout :
     ─ Sélection port + firmware path
     ─ 4 champs SSID / PWD des points d'accès AP1 / AP2
     ─ 3 boutons : Flasher, Lire, Appliquer
     ─ Log esptool (lecture seule)
     ─ Status bar (état global)
    """

    def __init__(self, view_model: Esp32DeployViewModel):
        # MainWindowBase attend (parent, default_width, default_height, name=None).
        # ViewBase stocke `self._view_model`, mais avec l'ordre de bases
        # (MainWindowBase, ViewBase[...]) le constructeur de ViewBase peut ne
        # pas être appelé via le super() chain selon l'implémentation du binding
        # Qt ; on assigne donc explicitement pour rester robuste.
        super().__init__(
            parent=None,
            default_width=640,
            default_height=560,
            view_model=view_model,
        )
        self._view_model: Esp32DeployViewModel = view_model
        self.setWindowTitle("Mir ESP Déploiement")
        self._build_ui()

        # --- Liaisons signaux du view_model ---
        self._view_model.ports_changed.connect(self._on_ports_changed)
        self._view_model.config_loaded.connect(self._on_config_loaded)
        self._view_model.status_changed.connect(self._on_status_changed)
        self._view_model.flash_finished.connect(self._on_flash_finished)
        self._view_model.state_changed.connect(self._on_state_changed)
        self._view_model.busy_changed.connect(self._on_busy_changed)

        # --- Liaisons inputs utilisateur -> view_model ---
        self._port_combo.currentIndexChanged.connect(self._on_port_changed)
        self._firmware_edit.textChanged.connect(self._on_firmware_path_changed)

        # Premier peuplement des ports (le VM scan automatiquement à l'init)
        self._on_ports_changed(self._view_model.get_available_ports())
        self._firmware_edit.setText(self._view_model.get_default_firmware_path())

    # -------------------------------------------------------------- construction
    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # Bloc 1 : port série + firmware ____________________________________
        target_group = QGroupBox("Cible")
        target_form = QFormLayout(target_group)

        # Port série : combo + bouton Rafraîchir
        port_row = QWidget()
        port_layout = QHBoxLayout(port_row)
        port_layout.setContentsMargins(0, 0, 0, 0)
        self._port_combo = QComboBox()
        self._port_combo.setEditable(False)
        self._port_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        port_layout.addWidget(self._port_combo, 1)

        self._refresh_action = self._make_action(
            DeployVMAction.REFRESH_PORTS,
            self._view_model.scan_ports,
            "",
            toolbar=None,
        )
        self._refresh_btn = QToolButton()
        self._refresh_btn.setDefaultAction(self._refresh_action)
        self._refresh_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        port_layout.addWidget(self._refresh_btn, 0)
        target_form.addRow("Port série", port_row)

        # Chemin firmware
        self._firmware_edit = QLineEdit()
        self._firmware_edit.setPlaceholderText("Chemin du firmware (.bin)")
        target_form.addRow("Firmware", self._firmware_edit)

        # Bloc 2 : AP1 / AP2 SSID + PWD ______________________________________
        wifi_group = QGroupBox("Identifiants Wi-Fi (AP1 / AP2)")
        wifi_form = QFormLayout(wifi_group)

        self._ap1_ssid_edit = QLineEdit()
        self._ap1_ssid_edit.setPlaceholderText("SSID du point d'accès primaire")
        wifi_form.addRow("AP1 SSID", self._ap1_ssid_edit)
        self._ap1_pwd_edit = QLineEdit()
        self._ap1_pwd_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._ap1_pwd_edit.setPlaceholderText("Mot de passe du point d'accès primaire")
        wifi_form.addRow("AP1 PWD", self._ap1_pwd_edit)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        wifi_form.addRow(sep)

        self._ap2_ssid_edit = QLineEdit()
        self._ap2_ssid_edit.setPlaceholderText("SSID du point d'accès secondaire (optionnel)")
        wifi_form.addRow("AP2 SSID", self._ap2_ssid_edit)
        self._ap2_pwd_edit = QLineEdit()
        self._ap2_pwd_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._ap2_pwd_edit.setPlaceholderText("Mot de passe du point d'accès secondaire")
        wifi_form.addRow("AP2 PWD", self._ap2_pwd_edit)

        # Bloc 3 : boutons d'action __________________________________________
        actions_group = QGroupBox("Actions")
        actions_layout = QHBoxLayout(actions_group)

        # Bouton "Flasher le firmware"
        self._flash_action = self._make_action(
            DeployVMAction.FLASH,
            self._on_flash_clicked,
            "",
            toolbar=None,
        )
        self._flash_btn = QToolButton()
        self._flash_btn.setDefaultAction(self._flash_action)
        self._flash_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        actions_layout.addWidget(self._flash_btn)

        # Bouton "Lire" : ESP -> champs
        self._read_action = self._make_action(
            DeployVMAction.READ_CFG,
            self._on_read_clicked,
            "",
            toolbar=None,
        )
        self._read_btn = QToolButton()
        self._read_btn.setDefaultAction(self._read_action)
        self._read_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        actions_layout.addWidget(self._read_btn)

        # Bouton "Appliquer" : champs -> ESP
        self._write_action = self._make_action(
            DeployVMAction.WRITE_CFG,
            self._on_write_clicked,
            "",
            toolbar=None,
        )
        self._write_btn = QToolButton()
        self._write_btn.setDefaultAction(self._write_action)
        self._write_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        actions_layout.addWidget(self._write_btn)

        # Bloc 4 : log esptool _______________________________________________
        log_group = QGroupBox("Log esptool")
        log_layout = QVBoxLayout(log_group)
        self._log_edit = QPlainTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setPlaceholderText(
            "Aucune opération lancée. La sortie de esptool apparaîtra ici."
        )
        font = self._log_edit.font()
        font.setFamily("Monospace")
        self._log_edit.setFont(font)
        log_layout.addWidget(self._log_edit)

        # Assemblage vertical ________________________________________________
        root.addWidget(target_group)
        root.addWidget(wifi_group)
        root.addWidget(actions_group)
        root.addWidget(log_group, 1)

        # Status bar
        self._status_label = QLabel("Prêt")
        self.statusBar().addWidget(self._status_label)

    # ----------------------------------------------------------- call helpers vm
    def _collect_ap_config(self) -> dict[str, str]:
        def s(edit: QLineEdit) -> str:
            return edit.text().strip()

        return {
            "AP1_SSID": s(self._ap1_ssid_edit),
            "AP1_PWD": s(self._ap1_pwd_edit),
            "AP2_SSID": s(self._ap2_ssid_edit),
            "AP2_PWD": s(self._ap2_pwd_edit),
        }

    # ------------------------------------------------------------------ handlers
    def _on_flash_clicked(self):
        self._log_edit.clear()
        self._status_label.setText("Flash en cours...")
        self._view_model.flash_firmware()

    def _on_read_clicked(self):
        self._status_label.setText("Lecture de la configuration Wi-Fi...")
        self._view_model.read_ap_configuration()

    def _on_write_clicked(self):
        self._status_label.setText("Envoi de la configuration Wi-Fi...")
        self._view_model.write_ap_configuration(self._collect_ap_config())

    def _on_port_changed(self, _index: int):
        self._view_model.set_selected_port(self._port_combo.currentText().strip())

    def _on_firmware_path_changed(self, text: str):
        self._view_model.set_firmware_path(text.strip())

    def _on_ports_changed(self, ports: list[str]):
        self._port_combo.blockSignals(True)
        self._port_combo.clear()
        if ports:
            self._port_combo.addItems(ports)
            self._port_combo.setCurrentIndex(0)
            self._view_model.set_selected_port(ports[0])
            self._status_label.setText(f"{len(ports)} port(s) série trouvé(s)")
        else:
            self._port_combo.addItem("(aucun port série détecté)")
            self._view_model.set_selected_port("")
            self._status_label.setText("Aucun port série détecté — branchez l'ESP32 puis rafraîchissez (F5)")
        self._port_combo.blockSignals(False)

    def _on_config_loaded(self, config: dict[str, str]):
        self._ap1_ssid_edit.setText(config.get("AP1_SSID", ""))
        self._ap1_pwd_edit.setText(config.get("AP1_PWD", ""))
        self._ap2_ssid_edit.setText(config.get("AP2_SSID", ""))
        self._ap2_pwd_edit.setText(config.get("AP2_PWD", ""))

    def _on_flash_finished(self, ok: bool, output: str):
        # Affiche toute la sortie capturée (stdout + stderr) ; utile même en cas
        # de succès (vérification post-flash) et indispensable en cas d'erreur.
        self._log_edit.appendPlainText(output)

    def _on_status_changed(self, status: str):
        self._status_label.setText(status)

    def _on_state_changed(self, _state: DeployState):
        # Effet visuel léger pour différencier l'état "occupé".
        if _state == DeployState.BUSY:
            self._log_edit.setStyleSheet("QPlainTextEdit { border: 2px solid #c79100; }")
        else:
            self._log_edit.setStyleSheet("")

    def _on_busy_changed(self, busy: bool):
        # Blocage "radical" des champs pour éviter les éditions en cours d'opération.
        self._firmware_edit.setEnabled(not busy)
        self._port_combo.setEnabled(not busy)
        self._ap1_ssid_edit.setEnabled(not busy)
        self._ap1_pwd_edit.setEnabled(not busy)
        self._ap2_ssid_edit.setEnabled(not busy)
        self._ap2_pwd_edit.setEnabled(not busy)
