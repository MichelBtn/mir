from PySide6 import QtWidgets, QtCore
from PySide6.QtWidgets import QLabel, QPushButton, QLineEdit, QGridLayout, QVBoxLayout, QHBoxLayout, QWidget
from .calibration_viewmodel import CalibrationViewModel, CalibrationMotorData
from mir_utils.ui.widgets import stylesheets, DialogBase

class CalibrationView(DialogBase):
    def __init__(self, parent:QWidget,view_model: CalibrationViewModel):
        super().__init__(parent)
        self._viewModel = view_model
        self.setWindowTitle("Calibration moteurs Feetech")
        self.header_style = "font-size: 11pt; margin-top: 20px"
        self.setup_ui()
        self._viewModel.pos_changed.connect(self.pos_changed_callback)
        self._viewModel.state_changed.connect(self.stage_changed_callback)
        self._viewModel.completed.connect(self.accept)
        self._viewModel.cancelled.connect(self.reject)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        #grille
        self.gridMotors = QGridLayout()
        self.fill_motors_grid()
        layout.addLayout(self.gridMotors)

        #titre étape
        layout.addSpacerItem(QtWidgets.QSpacerItem(0, 5, QtWidgets.QSizePolicy.Policy.Expanding))
        self.stageTitle = QLabel()
        self.stageTitle.setStyleSheet(self.header_style)
        layout.addWidget(self.stageTitle)

        #description étape
        self.stageDesc = QLabel()
        layout.addWidget(self.stageDesc)

        #boutons
        layout.addSpacerItem(QtWidgets.QSpacerItem(0, 15, QtWidgets.QSizePolicy.Policy.Expanding))
        buttons = QHBoxLayout()
        self.btnPrev = QPushButton("Précédent")
        self.btnPrev.clicked.connect(lambda : self._viewModel.prev())
        self.btnNext = QPushButton("Suivant")
        self.btnNext.clicked.connect(lambda : self._viewModel.next())
        self.btnEnd = QPushButton("Terminer")
        self.btnEnd.clicked.connect(lambda : self._viewModel.end())
        self.btnCancel = QPushButton("Annuler")
        self.btnCancel.clicked.connect(lambda : self._viewModel.cancel())
        buttons.addWidget(self.btnPrev)
        buttons.addWidget(self.btnNext)
        buttons.addWidget(self.btnEnd)
        buttons.addWidget(self.btnCancel)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.setLayout(layout)        

    def fill_motors_grid(self):
        def addHeader(text, col):
            label = QLabel(text, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet(self.header_style)
            self.gridMotors.addWidget(label, 0, col)    

        motors = self._viewModel.get_motors()
        addHeader("Motor", 0)
        addHeader("MIN", 1)
        addHeader("", 2)
        addHeader("HOME", 3)
        addHeader("", 4)
        addHeader("MAX", 5)
        addHeader("", 6)
        self.min_fields: dict[str, QLineEdit]= {}
        self.pos_fields: dict[str, QLineEdit]= {}
        self.max_fields: dict[str, QLineEdit]= {}
        self.min_fields_checks: dict[str, QLabel]= {}
        self.pos_fields_checks: dict[str, QLabel]= {}
        self.max_fields_checks: dict[str, QLabel]= {}
        for r, (name, motor) in enumerate(motors.items()):
            row = r + 1
            #nom du moteur
            self.gridMotors.addWidget(QLabel(f"{name} ID={motor.id}"), row, 0)
            #MIN
            min_field = QtWidgets.QLineEdit()
            min_field.setReadOnly(True)
            min_field.setFixedWidth(80)
            min_field.setStyleSheet(stylesheets.labels_style)
            min_field.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
            self.gridMotors.addWidget(min_field, row, 1)
            self.min_fields[name] = min_field
            min_field_check = QLabel(" ")
            self.gridMotors.addWidget(min_field_check, row, 2)
            self.min_fields_checks[name] = min_field_check
            #POS
            pos_field = QtWidgets.QLineEdit()
            pos_field.setReadOnly(True)
            pos_field.setFixedWidth(80)
            pos_field.setStyleSheet(stylesheets.labels_style)
            pos_field.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
            self.gridMotors.addWidget(pos_field, row, 3)
            self.pos_fields[name] = pos_field
            pos_field_check = QLabel(" ")
            self.gridMotors.addWidget(pos_field_check, row, 4)
            self.pos_fields_checks[name] = pos_field_check
            #MIN
            max_field = QtWidgets.QLineEdit()
            max_field.setReadOnly(True)
            max_field.setFixedWidth(80)
            max_field.setStyleSheet(stylesheets.labels_style)
            max_field.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
            self.gridMotors.addWidget(max_field, row, 5)
            self.max_fields[name] = max_field
            max_field_check = QLabel(" ")
            self.gridMotors.addWidget(max_field_check, row, 6)
            self.max_fields_checks[name] = max_field_check
        self.gridMotors.setColumnStretch(7, 1)                          

    def pos_changed_callback(self, datas: dict[str, CalibrationMotorData]):
        for name, data in datas.items():
            self.pos_fields[name].setText(str(data.home))
            self.min_fields[name].setText(str(data.min))
            self.max_fields[name].setText(str(data.max))
            self.min_fields_checks[name].setText("✔️" if data.min_checked  else "❗️")
            self.pos_fields_checks[name].setText("✔️" if data.home_checked else "❗️")
            self.max_fields_checks[name].setText("✔️" if data.max_checked else "❗️")

    def stage_changed_callback(self):
        self.btnPrev.setEnabled(self._viewModel.can_prev())
        self.btnNext.setEnabled(self._viewModel.can_next())
        self.btnEnd.setEnabled(self._viewModel.can_end())
        self.btnCancel.setEnabled(self._viewModel.can_cancel())
        self.stageTitle.setText(self._viewModel.stage_caption())
        self.stageDesc.setText(self._viewModel.stage_description())
