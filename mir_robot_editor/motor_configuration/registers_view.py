from PySide6 import QtWidgets, QtCore
from PySide6.QtWidgets import QLabel, QPushButton, QLineEdit, QCheckBox, QHBoxLayout, QVBoxLayout, QRadioButton, QWidget, QScrollArea
from mir_robot_editor.motor_configuration.registers_viewmodel import RegistersViewModel, Register
from mir_utils.ui.widgets import stylesheets, DialogBase


class RegistersView(DialogBase):
    def __init__(self, parent:QWidget, view_model: RegistersViewModel):
        super().__init__(parent)
        self._viewModel = view_model
        self.setWindowTitle(view_model.get_title())
        self.fields = {}
        self.setup_ui()
        self._viewModel.set_update_callback(self.callback)

    def setup_ui(self):
        layout = QVBoxLayout()

        buttons = QHBoxLayout()
        self._b_sort_by_name = QRadioButton("Trier par nom")
        self._b_sort_by_address = QRadioButton("Trier par adresse")
        buttons.addWidget(self._b_sort_by_name)
        buttons.addWidget(self._b_sort_by_address)
        self._b_sort_by_name.setChecked(True)
        self._b_sort_by_name.toggled.connect(self.fill_registers_layout)
        buttons.addStretch()
        layout.addLayout(buttons)
        layout.addSpacerItem(QtWidgets.QSpacerItem(0, 10, QtWidgets.QSizePolicy.Policy.Expanding))

        container = QWidget()
        self._registers_layout = QHBoxLayout(container)
        scroll = QScrollArea()
        scroll.setWidget(container)
        scroll.setWidgetResizable(True)
        self.fill_registers_layout()
        layout.addWidget(scroll)

        self.setLayout(layout)


    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self.clear_layout(item.layout())

    def fill_registers_layout(self):
        while self._registers_layout.count() > 0:  # on garde le spacer (dernier item)
            item = self._registers_layout.takeAt(0)
            if item.layout():
                self.clear_layout(item.layout())
        self.rows = self._viewModel.get_rows(self._b_sort_by_name.isChecked())
        count = len(self.rows)
        start = 0
        NROWS=28
        end = NROWS 
        while True:
            grid = self.make_grid(start, end)
            if (end - start) < NROWS:
                for i in [end, NROWS - (end - start) - 1]:
                    grid.addWidget(QLabel(), i, 0)
            self._registers_layout.addLayout(grid)
            start += NROWS
            end += NROWS
            if start > count - 1:
                break
            if end > count:
                end = count
        

    def make_grid(self, a, b):
        grid = QtWidgets.QGridLayout()
        for index, col_name in enumerate(self._viewModel.get_columns_names()):
            label = QLabel(col_name, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(label, 0, index)    
        for index, row in enumerate(self.rows[a:b]):
            row_index = index + 1
            lbl_name = QLabel(row.name)
            grid.addWidget(lbl_name, row_index, 0)
            lbl_reg = QLabel(str(row.address))
            grid.addWidget(lbl_reg, row_index, 1)
            lbl_size = QLabel(str(row.size))
            grid.addWidget(lbl_size, row_index, 2)
            if row.type == "bool":
                cb_value = QCheckBox()
                cb_value.setChecked(row.value == "1")
                self.fields[row.name] = cb_value
                grid.addWidget(cb_value, row_index, 3)
                cb_value.setEnabled(not row.read_only)
            else:
                tb_value = QLineEdit()
                tb_value.setText(row.value)
                tb_value.setReadOnly(row.read_only)
                tb_value.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
                if row.read_only:
                    tb_value.setStyleSheet(stylesheets.css_text_disabled)
                else:
                    tb_value.setStyleSheet(stylesheets.css_text_enabled)
                tb_value.setFixedWidth(80)
                self.fields[row.name] = tb_value
                grid.addWidget(tb_value, row_index, 3)
            if not row.read_only:
                btn_apply = QPushButton("➡️")
                btn_apply.setFixedSize(24,24)
                btn_apply.setStyleSheet(stylesheets.css_button)
                btn_apply.setEnabled(not row.read_only)
                btn_apply.clicked.connect(lambda _, n=row.name: self.apply(n))
                grid.addWidget(btn_apply, row_index, 4)
        grid.setColumnMinimumWidth(5, 30)  
        grid.setColumnStretch(5, 0)  
        return grid

    def apply(self, reg_name:str):
        field = self.fields[reg_name]
        if isinstance(field, QCheckBox):
            value = 1 if field.isChecked() else 0
        else:
            value = int(field.text())
        self._viewModel.write(reg_name, value)            
           

    def callback(self, row:Register):
        if row.type == "bool":
            self.fields[row.name].setChecked(row.value == "1")
        else:
            self.fields[row.name].setText(row.value)
        
