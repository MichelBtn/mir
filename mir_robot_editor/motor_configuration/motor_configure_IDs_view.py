from PySide6 import QtCore
from mir_utils.ui.widgets import DialogBase
from PySide6.QtWidgets import QLabel, QPushButton, QLineEdit, QHBoxLayout, QGridLayout, QVBoxLayout, QDialog
from PySide6.QtCore import Qt 
from mir_utils.ui.widgets import stylesheets
from mir_robot_editor.motor_configuration.motor_configure_IDs_view_model import ChangeIDViewModel
from mir_robot_editor.motor_configuration.motor_configure_IDs_view_model import MotorConfigureIDsViewModel, MotorData
    
class ChangeIDView(QDialog):
    def __init__(self, parent, viewModel: ChangeIDViewModel):
        super().__init__(parent)
        self._viewModel = viewModel
        self.setWindowTitle("Changer l'ID du moteur")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Changer l'ID d'un moteur perturbera les configurations existantes\r\nEnvisagez de devoir reconfigurer et recalibrer"))
        grid = QGridLayout(self)
        grid.addWidget(QLabel("ID courant"), 0, 0)
        tbCurrentID = QLineEdit(str(self._viewModel.get_current_id()))
        tbCurrentID.setReadOnly(True)
        grid.addWidget(tbCurrentID, 0, 1)
        grid.addWidget(QLabel("Nouvel ID"), 1, 0)
        self.tbNewID = QLineEdit(str(self._viewModel.get_current_id()))
        grid.addWidget(self.tbNewID, 1, 1)        
        grid.setColumnStretch(2, 1)                            
        layout.addLayout(grid)

        buttons = QHBoxLayout()
        self.btnApply = QPushButton("Appliquer")
        self.btnApply.setStyleSheet(stylesheets.css_button)
        self.btnApply.clicked.connect(self.apply_click)
        buttons.addWidget(self.btnApply)
        btnCancel = QPushButton("Annuler")
        btnCancel.setStyleSheet(stylesheets.css_button)
        btnCancel.clicked.connect(self.cancel_click)
        buttons.addWidget(btnCancel)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.setLayout(layout)

    def apply_click(self):
        if self._viewModel.set_new_id(int(self.tbNewID.text())):
            self.close()

    def cancel_click(self):
        self.close()

class MotorConfigureIDsView(DialogBase):
    def __init__(self, parent, viewModel:MotorConfigureIDsViewModel):
        super().__init__(parent)
        self._viewModel :MotorConfigureIDsViewModel = viewModel
        self.setup_ui()
        self._viewModel.property_changed.connect(self.on_property_changed)   
        self.fill_grid_motors(self._viewModel.get_motors_data())
        
    def on_property_changed(self, property_name, property_value):
        if property_name == "bus_created":
            self.fill_grid_motors(property_value)
        elif property_name == "data_changed":
            self.on_motor_data_changed(property_value)

    def setup_ui(self):
        self.setWindowTitle("Configuration des IDs moteurs")
        main_layout = QVBoxLayout(self)
        self.gridMotors = QGridLayout()
        main_layout.addLayout(self.gridMotors)
        main_layout.addStretch()
        btn_close = QPushButton("Terminer")
        btn_close.clicked.connect(self.close)
        main_layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignCenter)

    def fill_grid_motors(self, motors_dict: dict[str, MotorData]|None):
        def addHeader(text, col):
            label = QLabel(text, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet(stylesheets.header_style)
            self.gridMotors.addWidget(label, 0, col)    
        self.header_fields: dict[str, QLabel]= {}
        self.pos_fields: dict[str, QLineEdit]= {}
        addHeader("Moteur", 0)
        addHeader("Position", 1)
        if motors_dict is None:
            return
        for r, (name, motor) in enumerate(motors_dict.items()):
            row = r + 1
            #nom du moteur
            header = QLabel(f"{name} ID={motor.id}")
            self.header_fields[name] = header
            self.gridMotors.addWidget(header, row, 0)
            #position
            pos_field = QLineEdit()
            pos_field.setReadOnly(True)
            pos_field.setFixedWidth(80)
            pos_field.setStyleSheet(stylesheets.labels_style)
            pos_field.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
            self.gridMotors.addWidget(pos_field, row, 1)
            self.pos_fields[name] = pos_field
            #Set ID
            btnSetID = QPushButton("Changer ID...")
            btnSetID.clicked.connect(lambda _, n = name: self.change_motor_id(n))
            self.gridMotors.addWidget(btnSetID, row, 5) 
            
        self.gridMotors.setColumnStretch(6, 1)                  
        self.gridMotors.setEnabled(False)  

    def on_motor_data_changed(self, motors_dict: dict[str, MotorData]):
        for motor in motors_dict.values():
            self.pos_fields[motor.name].setText(str(motor.pos))
            self.header_fields[motor.name].setText(f"{motor.name} ID={motor.id}")

    def change_motor_id(self, name:str):
        self._viewModel.execute_change_motor_id(lambda vm : ChangeIDView(self, vm).exec(), name)


