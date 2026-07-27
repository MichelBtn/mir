from typing_extensions import override
from mir_utils.ui.dialogs import IDialogProvider
from PySide6.QtCore import Signal, QTimer
from mir_devices.mir_feetech_motor_bus import mirFeetechMotorsBus, mirMotorBusConfiguration
from mir_utils.concurrency import BackgroundWorker
from dataclasses import dataclass
from mir_utils.ui.view_model_base import ViewModelBase
from mir_utils.ui.dialogs import IDialogProvider

@dataclass
class MotorData():
    name: str = ""
    id: int = 0
    pos: int = 0

class ChangeIDViewModel(ViewModelBase):
    def __init__(self, motor_name: str, motors_data: dict[str, MotorData], dialogProvider: IDialogProvider):      
        self._motor_name = motor_name
        self._motors_data = motors_data
        self._current_id = motors_data[motor_name].id
        self._new_id = self._current_id
        self._dialogProvider = dialogProvider
        self._id_has_changed = False

    def _enter_context(self):
        pass
    
    def _exit_context(self, exc_type, exc_value, traceback):
        pass 
    
    def get_current_id(self):
        return self._current_id

    def get_new_id(self):
        return self._new_id

    def get_title(self):
        return f"Changer l'ID de {self._motor_name}"

    def id_has_been_changed(self):
        return self._id_has_changed

    def set_new_id(self, new_id:int)->bool:
        if new_id == self._current_id:
            self._dialogProvider.information("Appliquer ID", "L'ID doit être différent de l'ID courant")
            return False
        if new_id < 1 or new_id > 253:
            self._dialogProvider.information("Appliquer ID", "L'ID doit être compris entre 1 et 253")
            return False
        self._new_id = new_id
        for key, motor in self._motors_data.items():
            if motor.id == new_id and key != self._motor_name:
                self._dialogProvider.information("Appliquer ID", "L'ID est déjà utilisé par un autre moteur")
                return False
        self._id_has_changed = True
        return True

class MotorConfigureIDsViewModel(ViewModelBase):
    property_changed = Signal(str, object)

    def __init__(self, dialogProvider : IDialogProvider, config:mirMotorBusConfiguration):
        super().__init__(dialogProvider)
        self._dialogProvider = dialogProvider
        self._config = config
        self._timer = QTimer()
        self._timer.timeout.connect(self.on_timer)
        self._worker = BackgroundWorker(max_workers=1)
        self._bus: mirFeetechMotorsBus = mirFeetechMotorsBus(self._config)
        self._bus.mir_connect()
        self._bus.mir_configure_motors()
        self._timer.start(200)
        self._motors_data = {key: MotorData(name=key, id=motor.id) for key, motor in self._config.motors.items()}    
        motors_pos = self._bus.mir_read_positions()
        for key in self._motors_data:
            self._motors_data[key].pos = int(motors_pos[key])
            self._bus.mir_write_register_by_id("Torque_Enable", self._motors_data[key].id, 0)

    def get_motors_data(self) -> dict[str, MotorData]|None:
        return self._motors_data

    @override
    def _enter_context(self):
        pass

    @override
    def _exit_context(self, exc_type, exc_value, traceback):
        self._timer.stop()
        self._worker.shutdown()
        self._bus.mir_disconnect()

    def on_timer(self):
        for key, motor in self._motors_data.items():
            position = self._bus.mir_read_register_by_id("Present_Position", motor.id)
            self._motors_data[key].pos = position
        self.property_changed.emit("data_changed", self._motors_data)

    def execute_change_motor_id(self, open_view, name:str):
        self._timer.stop()
        vm = ChangeIDViewModel(name, self._motors_data, self._dialogProvider)
        with vm:
            open_view(vm)
        if vm.id_has_been_changed():
            self.apply_motor_id(name, vm.get_new_id())
            self._id_has_changed = True
        self._timer.start(200)            

    def has_id_changed(self):
        return hasattr(self, "_id_has_changed") and self._id_has_changed

    def apply_motor_id(self, motor_name, new_id: int):
        try:            
            self._bus.mir_write_register_by_id("Lock", self._motors_data[motor_name].id, 0)
            self._bus.mir_write_register_by_id("ID", self._motors_data[motor_name].id, new_id)
            self._bus.mir_write_register_by_id("Lock", motor_id=new_id, value=1)
            self._motors_data[motor_name].id = new_id
            return True
        except Exception as e:
            self._dialogProvider.information("Appliquer ID", f"Erreur lors de l'application de l'ID : {e}")
            return False        