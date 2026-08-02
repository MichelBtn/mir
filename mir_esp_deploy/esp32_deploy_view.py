from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QToolButton
)
from PySide6.QtCore import Qt, Signal
from mir_utils.ui.view_base import ViewBase
from mir_utils.ui.widgets import MainWindowBase
from mir_esp_deploy.esp32_deploy_view_model import Esp32DeployViewModel, DeployVMAction


class PasswordEdit(QWidget):
    textChanged = Signal(str)
    returnPressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._line_edit = QLineEdit(self)
        self._line_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._line_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        
        self._toggle_button = QToolButton(self)
        self._toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_button.setCheckable(True)
        self._toggle_button.setChecked(False)
        self._toggle_button.setToolTip("Afficher le mot de passe")
        self._toggle_button.setIcon(ViewBase.find_icon("eye_off"))
        self._toggle_button.setFixedWidth(32)          # largeur fixe → taille stable
        self._toggle_button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Preferred
        )
        # Optionnel : taille d’icône si vous utilisez des QIcon
        # self._toggle_button.setIconSize(QSize(16, 16))

        self._toggle_button.toggled.connect(self._on_toggled)
        self._line_edit.textChanged.connect(self.textChanged.emit)
        self._line_edit.returnPressed.connect(self.returnPressed.emit)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._line_edit)
        layout.addWidget(self._toggle_button)

        self.setStyleSheet("""
            PasswordEdit QLineEdit {
                border-top-right-radius: 0;
                border-bottom-right-radius: 0;
            }
            PasswordEdit QToolButton {
                border-top-left-radius: 0;
                border-bottom-left-radius: 0;
                padding: 0;
            }
        """)

    def _on_toggled(self, checked: bool):
        if checked:
            self._line_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self._toggle_button.setToolTip("Masquer le mot de passe")
            self._toggle_button.setIcon(ViewBase.find_icon("eye_on"))
        else:
            self._line_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._toggle_button.setToolTip("Afficher le mot de passe")
            self._toggle_button.setIcon(ViewBase.find_icon("eye_off"))

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------
    def text(self) -> str:
        return self._line_edit.text()

    def setText(self, text: str):
        self._line_edit.setText(text)

    def clear(self):
        self._line_edit.clear()

    def setPlaceholderText(self, text: str):
        self._line_edit.setPlaceholderText(text)

    def placeholderText(self) -> str:
        return self._line_edit.placeholderText()

    def setMaxLength(self, length: int):
        self._line_edit.setMaxLength(length)

    def setReadOnly(self, readonly: bool):
        self._line_edit.setReadOnly(readonly)

    def isReadOnly(self) -> bool:
        return self._line_edit.isReadOnly()

    def setEchoMode(self, mode: QLineEdit.EchoMode):
        self._line_edit.setEchoMode(mode)
        self._toggle_button.setChecked(mode == QLineEdit.EchoMode.Normal)

    def echoMode(self) -> QLineEdit.EchoMode:
        return self._line_edit.echoMode()

    def lineEdit(self) -> QLineEdit:
        return self._line_edit

    def setFocus(self, reason=Qt.FocusReason.OtherFocusReason):
        self._line_edit.setFocus(reason)
        
class Esp32DeployView(MainWindowBase, ViewBase[Esp32DeployViewModel, DeployVMAction]):
    """Vue de l'outil de déploiement ESP32."""

    def __init__(self, view_model: Esp32DeployViewModel):
        super().__init__(
            parent=None,
            default_width=580,
            default_height=620,
            view_model=view_model,
        )
        self._can_close = True
        self._view_model: Esp32DeployViewModel = view_model
        self.setWindowTitle("Mir ESP Déploiement")
        self._build_ui()

        # Liaisons signaux VM → Vue
        self._view_model.config_loaded.connect(self._on_config_loaded)
        self._view_model.status_changed.connect(self._on_status_changed)
        self._view_model.log_added.connect(self._on_flash_output_received)
        self._view_model.busy_changed.connect(self._on_busy_changed)

        # Liaisons Vue → VM
        self._port_combo.currentIndexChanged.connect(self._on_port_changed)
        self._baud_combo.currentIndexChanged.connect(self._on_baud_rate_changed)

        # Initialisation
        self.update_ports(self._view_model.scan_ports())

    # --------------------------------------------------------------- construction
    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # --- Port série + firmware ---
        target_group = QGroupBox("Cible")
        target_form = QFormLayout(target_group)

        port_row = QWidget()
        port_layout = QHBoxLayout(port_row)
        port_layout.setContentsMargins(0, 0, 0, 0)
        self._port_combo = QComboBox()
        self._port_combo.setEditable(False)
        self._port_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        port_layout.addWidget(self._port_combo, 1)

        self._refresh_btn = QPushButton("Rafraîchir")
        self._refresh_btn.clicked.connect(lambda : self.update_ports(self._view_model.scan_ports()))
        self._view_model.get_action(DeployVMAction.REFRESH_PORTS).action_state_changed.connect(
            self._refresh_btn.setEnabled
        )
        port_layout.addWidget(self._refresh_btn)
        target_form.addRow("Port série", port_row)

        self._baud_combo = QComboBox()
        self._baud_combo.setEditable(False)
        for key, val in self._view_model.get_serial_configurations().items():
            self._baud_combo.addItem(key, val)
        # Sélectionner la valeur courante du VM
        current_serial_cfg = self._view_model.get_serial_configuration()
        self._baud_combo.setCurrentText(current_serial_cfg)
        target_form.addRow("Modèle ESP32", self._baud_combo)

        # --- Identifiants Wi-Fi ---
        wifi_group = QGroupBox("Identifiants Wi-Fi")
        wifi_form = QFormLayout(wifi_group)

        self._ap1_ssid_edit = QLineEdit()
        self._ap1_ssid_edit.setPlaceholderText("SSID du point d'accès primaire")
        wifi_form.addRow("AP1 SSID", self._ap1_ssid_edit)

        self._ap1_pwd_edit = PasswordEdit()
        self._ap1_pwd_edit.setPlaceholderText("Mot de passe AP1")
        wifi_form.addRow("AP1 PWD", self._ap1_pwd_edit)

        self._btn_swap_ap = QToolButton()
        self._btn_swap_ap.setIcon(ViewBase.find_icon("swap"))
        self._btn_swap_ap.clicked.connect(self._on_swap_ap_clicked)
        wifi_form.addRow(self._btn_swap_ap)

        self._ap2_ssid_edit = QLineEdit()
        self._ap2_ssid_edit.setPlaceholderText("SSID du point d'accès secondaire")
        wifi_form.addRow("AP2 SSID", self._ap2_ssid_edit)

        self._ap2_pwd_edit = PasswordEdit()
        self._ap2_pwd_edit.setPlaceholderText("Mot de passe AP2")
        wifi_form.addRow("AP2 PWD", self._ap2_pwd_edit)

        # --- Boutons d'action ---
        actions_group = QGroupBox("Actions")
        actions_layout = QHBoxLayout(actions_group)

        self._flash_btn = QPushButton("Mettre à jour le firmware")
        self._flash_btn.clicked.connect(self._on_flash_clicked)
        self._view_model.get_action(DeployVMAction.FLASH).action_state_changed.connect(
            self._flash_btn.setEnabled
        )
        self._flash_btn.setEnabled(False)
        actions_layout.addWidget(self._flash_btn)

        self._read_btn = QPushButton("Lire config Wi-Fi")
        self._read_btn.clicked.connect(self._on_read_clicked)
        self._view_model.get_action(DeployVMAction.READ_CFG).action_state_changed.connect(
            self._read_btn.setEnabled
        )
        self._read_btn.setEnabled(False)
        actions_layout.addWidget(self._read_btn)

        self._write_btn = QPushButton("Appliquer config Wi-Fi")
        self._write_btn.clicked.connect(self._on_write_clicked)
        self._view_model.get_action(DeployVMAction.WRITE_CFG).action_state_changed.connect(
            self._write_btn.setEnabled
        )
        self._write_btn.setEnabled(False)
        actions_layout.addWidget(self._write_btn)

        # --- Log esptool ---
        log_group = QGroupBox("Logs")
        log_layout = QVBoxLayout(log_group)
        self._log_edit = QPlainTextEdit()
        self._log_edit.setReadOnly(True)
        font = self._log_edit.font()
        font.setFamily("Monospace")
        self._log_edit.setFont(font)
        log_layout.addWidget(self._log_edit)

        # Assemblage
        root.addWidget(target_group)
        root.addWidget(wifi_group)
        root.addWidget(actions_group)
        root.addWidget(log_group, 1)

        # Status bar
        self._status_label = QLabel("Prêt")
        self.statusBar().addWidget(self._status_label)

    def closeEvent(self, event):
        if self._can_close:
            return super().closeEvent(event)
        event.ignore()

    # ------------------------------------------------------------ collecte config
    def _collect_ap_config(self) -> dict[str, str]:
        return {
            "ap1_ssid": self._ap1_ssid_edit.text().strip(),
            "ap1_pwd": self._ap1_pwd_edit.text().strip(),
            "ap2_ssid": self._ap2_ssid_edit.text().strip(),
            "ap2_pwd": self._ap2_pwd_edit.text().strip(),
        }

    # ------------------------------------------------------------------- handlers
    def _on_swap_ap_clicked(self):
        ap1ssid = self._ap1_ssid_edit.text()
        ap1pwd = self._ap1_pwd_edit.text()
        self._ap1_ssid_edit.setText(self._ap2_ssid_edit.text())
        self._ap1_pwd_edit.setText(self._ap2_pwd_edit.text())
        self._ap2_ssid_edit.setText(ap1ssid)
        self._ap2_pwd_edit.setText(ap1pwd)

    def _on_flash_clicked(self):
        self._log_edit.clear()
        self._view_model.flash_firmware()

    def _on_read_clicked(self):
        self._view_model.read_ap_configuration()

    def _on_write_clicked(self):
        self._view_model.write_ap_configuration(self._collect_ap_config())

    def _on_port_changed(self, _index: int):
        self._view_model.set_selected_port(self._port_combo.currentText().strip())

    def _on_baud_rate_changed(self, _index: int):
        serial_cfg = self._baud_combo.currentText()
        if serial_cfg is not None:
            self._view_model.set_serial_configuration(serial_cfg)

    def update_ports(self, ports: list[str]):
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
            self._status_label.setText("Aucun port série détecté")
        self._port_combo.blockSignals(False)

    def _on_config_loaded(self, config: dict[str, str]):
        self._ap1_ssid_edit.setText(config.get("ap1_ssid", ""))
        self._ap1_pwd_edit.setText(config.get("ap1_pwd", ""))
        self._ap2_ssid_edit.setText(config.get("ap2_ssid", ""))
        self._ap2_pwd_edit.setText(config.get("ap2_pwd", ""))

    def _on_flash_output_received(self, output: str):
        self._log_edit.appendPlainText(output)

    def _on_status_changed(self, status: str):
        self._status_label.setText(status)

    def _on_busy_changed(self, busy: bool):
        self._port_combo.setEnabled(not busy)
        self._baud_combo.setEnabled(not busy)
        self._ap1_ssid_edit.setEnabled(not busy)
        self._ap1_pwd_edit.setEnabled(not busy)
        self._ap2_ssid_edit.setEnabled(not busy)
        self._ap2_pwd_edit.setEnabled(not busy)
        self._refresh_btn.setEnabled(not busy)
        self._btn_swap_ap.setEnabled(not busy)
        self._can_close = not busy
