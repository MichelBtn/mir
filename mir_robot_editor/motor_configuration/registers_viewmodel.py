from PySide6 import QtCore
from mir_devices.mir_feetech_motor_bus import sts3215_registers, Register
from mir_utils.ui.view_model_base import ViewModelBase
from mir_devices.mir_feetech_motor_bus import ImirFeetechMotorBus
import time
from mir_utils.metrics import SimpleMovingAverage

class RegistersViewModel(ViewModelBase):

    def __init__(self, bus: ImirFeetechMotorBus, motor_name: str):
        self._bus = bus
        self._motor_name = motor_name
        self._registers = sts3215_registers
        self._rows: list[Register] = list(self._registers.values())
        self._rows_sorted_by_name = sorted(self._rows, key=lambda x: x.name)
        self.callback = None
        self.timer = QtCore.QTimer()
        self._moving_average = SimpleMovingAverage(10)
        self._counter = 0

    def _enter_context(self):
        self.timer.timeout.connect(self.update_fields)
        
    def _exit_context(self, exc_type, exc_value, traceback): 
        self.timer.stop()
           
    def set_update_callback(self, callback):
        self.callback = callback
        self.timer.start(500)

    def get_title(self):
        return f"Registres de {self._motor_name}"

    def get_columns_names(self):
        return ["Description", "Address", "Size", "Current value"]

    def get_rows(self, sort_by_name=True):
        rows = self._rows_sorted_by_name if sort_by_name else self._rows
        for row in rows:
            try:
                value = self._bus.mir_read_register(row.name, self._motor_name)
                row.set_value(str(value))
            except Exception:
                row.set_value("error")
        return rows

    def update_fields(self, read_all=False):
        self._check_initialized()
        t0 = time.perf_counter()
        for reg in self._rows:
            if read_all or reg.read_only:
                value = self._bus.mir_read_register(reg.name, self._motor_name)
                reg.set_value(str(value))
                if self.callback is not None:
                    self.callback(reg)
        t1 = time.perf_counter()
        self._moving_average.add(t1-t0)
        self._counter += 1
        if self._counter % 10 == 0:
            print(f"Temps de mise à jour moyen: {self._moving_average.average()*1000:.0f}ms")

    def write(self, reg_name:str, value):
        reg = self._registers[reg_name]
        self._bus.mir_write_register(reg_name, self._motor_name, value)
        value = self._bus.mir_read_register(reg_name, self._motor_name)
        reg.set_value(str(value))   
        self.update_fields(read_all=True)
        