from loguru import logger
import traceback
from enum import Enum, auto
from typing import Any
import time
from pathlib import Path
from threading import Lock
from PySide6.QtCore import Signal
from mir_devices.mir_device import DeviceAction, ObservablePropertyFloat, ObservablePropertyConverter
from mir_utils.metrics import SimpleMovingAverage, Stats, DataRecorder
from mir_utils.period_waiters import PeriodWaiterExact
from mir_utils.concurrency import BackgroundWorker
from mir_robot.mir_robot import mirRobot
from mir_devices.mir_device import ActionValue
from mir_utils.ui.view_model_base import VMAction, ViewModelBase

class RobotMonitorVMAction(Enum):
    APPLY = auto()
    START = auto()
    STOP = auto()
    ACTION = auto()

class FpsStats:
    def __init__(self, parent):
        self.parent = parent
        self.avg = SimpleMovingAverage(50)
        self.last_time_sent_stats = 0.0
        self.stats = Stats()

    def update(self, t0: float, t:float):
        self.avg.add(1/(t-t0))
        self.stats.add(t-t0)
        if (t - self.last_time_sent_stats) >= 0.1:  # Envoyer les statistiques toutes les secondes
            self.parent.fps_changed.emit(self.avg.average(), self.stats.get())
            self.last_time_sent_stats = t

class RobotMonitorViewModel(ViewModelBase[RobotMonitorVMAction]):
    observations_list_changed = Signal(list)
    actions_list_changed = Signal(dict)
    observation_ready = Signal(dict) #clé, dictionnaire d'observations, timestamp en sec
    observations_accepted = Signal(dict)
    busy_state_changed = Signal(bool)
    fps_changed = Signal(float,dict)

    def __init__(self, dialog_provider):
        super().__init__(dialog_provider)
        self._observation_recorder : DataRecorder | None = None
        self._worker = BackgroundWorker()
        self._last_action_lock = Lock()
        self._last_action : dict[str, Any ] | None = None
        self._stop_loop = False
        self._robot: mirRobot | None = None
        self._is_loop_running = False
        self._actions[RobotMonitorVMAction.APPLY] = VMAction("Appliquer", "Appliquer les observations à activer")
        self._actions[RobotMonitorVMAction.START] = VMAction("Démarrer les observations", "Démarrer les observations")
        self._actions[RobotMonitorVMAction.STOP] = VMAction("Arrêter les observations", "Arrêter les observations")
        self._actions[RobotMonitorVMAction.ACTION] = VMAction("", "")

    def _enter_context(self):
        pass

    def _exit_context(self, exc_type, exc_value, traceback):
        self._worker.shutdown()

    def get_robot_action(self)-> dict[str, ActionValue] | None:
        with self._last_action_lock:
            if self._last_action:
                last_action = self._last_action.copy()
                self._last_action = None
                return last_action
            return None
        
    def set_robot_action(self, action: dict[str, ActionValue]):
        with self._last_action_lock:
            self._last_action = action.copy()

    def _loop(self)->None:
        if self._robot is None:
            raise RuntimeError("Le robot n'est pas connecté, impossible de démarrer la boucle")
        self.busy_state_changed.emit(True)
        fps_stats : FpsStats | None = FpsStats(self) if self._fps_stats_enabled else None
        t0 = time.perf_counter()
        PERIOD = 1/self._fps
        time.sleep(PERIOD)
        period_waiter = PeriodWaiterExact(PERIOD)
        while not self._stop_loop:
            t = time.perf_counter()
            if fps_stats is not None: 
                fps_stats.update(t0, t)
            t0 = t
            observations: dict[str, Any] = self._robot.get_observation()
            if self._observation_recorder is not None:
                self._observation_recorder.append(observations)
            self.observation_ready.emit(observations)
            action:dict[str, ActionValue]|None = self.get_robot_action()
            if action:
                self._robot.send_action(action)
            period_waiter.wait()
            
    def _on_loop_finished(self, result:None):
        if self._robot is not None:
            self._robot.motors_stop()
        self._is_loop_running = False
        self._actions[RobotMonitorVMAction.APPLY].set_enabled(True)   
        self._actions[RobotMonitorVMAction.START].set_enabled(True)   
        self._actions[RobotMonitorVMAction.STOP].set_enabled(False)   
        self._actions[RobotMonitorVMAction.ACTION].set_enabled(False)   
        if self._observation_recorder is not None:
            path = Path(__file__).parent.parent / "data/rec.npz"
            self._observation_recorder.save(path)
        self.busy_state_changed.emit(False)

    def _on_loop_failed(self, error: Exception):
        self._is_loop_running = False
        traceback_str = "".join(traceback.format_exception(error))
        logger.error(error)
        logger.error(traceback_str)
        self._actions[RobotMonitorVMAction.APPLY].set_enabled(True)   
        self._actions[RobotMonitorVMAction.START].set_enabled(True)   
        self._actions[RobotMonitorVMAction.STOP].set_enabled(False)   
        self._actions[RobotMonitorVMAction.ACTION].set_enabled(False)   
        self.busy_state_changed.emit(False)

    def connect_to_robot(self, robot : mirRobot):
        self._robot = robot
        self._observables = robot.get_observables()
        self._selected_observables = {}
        actions = robot.get_actions()
        for action in actions.values():
            action.set_value(round(action.get_value(), 2))
        self.actions_list_changed.emit(actions)
        
        self.observations_list_changed.emit([key for key in robot.observation_features.keys()])
        self._actions[RobotMonitorVMAction.APPLY].set_enabled(True)
        self._actions[RobotMonitorVMAction.ACTION].set_enabled(False)   

    def disconnect_from_robot(self):
        if self._is_loop_running is True:
            raise RuntimeError("La boucle de lecture est en cours d'exécution")
        for action in self._actions.values():
            action.set_enabled(False)
        self._robot = None
        self._selected_observables = {}
        self.observations_accepted.emit(self._selected_observables)     
        self.observations_list_changed.emit([])
        self.actions_list_changed.emit({})
        self._actions[RobotMonitorVMAction.APPLY].set_enabled(False)   
        self._actions[RobotMonitorVMAction.START].set_enabled(False)   
        self._actions[RobotMonitorVMAction.STOP].set_enabled(False)   
        self._actions[RobotMonitorVMAction.ACTION].set_enabled(False)   

    def apply_observations(self, selected_observables_keys: list[str]):
        self._selected_observables = {name: self._observables[name] for name in selected_observables_keys}
        self.observations_accepted.emit(self._selected_observables)   
        if self._robot is None:
            raise RuntimeError("Le robot n'a pas été créé")  
        self._robot.select_observables(self._selected_observables)        
        self._actions[RobotMonitorVMAction.START].set_enabled(True)   
        
    def stop(self):
        if self._is_loop_running is True:
            self._stop_loop = True
        self._actions[RobotMonitorVMAction.ACTION].set_enabled(False)    
           

    def start(self, fps_str: str, fps_stats_enabled: bool, observations_recording_enabled: bool):
        if self._is_loop_running is True:
            return              
        self._fps_stats_enabled = fps_stats_enabled
        try:  
            self._fps = int(fps_str)
            if self._fps < 10 or self._fps > 1000:
                raise ValueError()
        except Exception:
            self._dialogProvider.warning("Valeur fps invalide", "La valeur de fps doit être un entier entre 10 et 1000")
            return
        self._observations_recording_enabled = observations_recording_enabled
        if observations_recording_enabled:
            record_max_duration = 600
            observables = {name:prop for name,prop in self._observables.items() if isinstance(prop, ObservablePropertyFloat)}
            total_size = 0
            capacity = record_max_duration * self._fps
            for obs in observables.values():
                float_size = obs.dtype.itemsize 
                total_size += float_size * capacity
            self._observation_recorder = DataRecorder(ObservablePropertyConverter.observables_to_dict(self._selected_observables), capacity)
        self._stop_loop = False
        self._is_loop_running = True
        self._actions[RobotMonitorVMAction.APPLY].set_enabled(False)   
        self._actions[RobotMonitorVMAction.START].set_enabled(False)   
        self._actions[RobotMonitorVMAction.STOP].set_enabled(True)   
        self._actions[RobotMonitorVMAction.ACTION].set_enabled(True)   
        self._worker.run(self._loop, self._on_loop_finished, self._on_loop_failed, self)
        
    def on_emergency_stop_clicked(self):
        if self._robot is None:
            raise RuntimeError("Le robot n'a pas été créé")  
        self._robot.motors_emergency_stop()

    def on_motor_action_changed(self, motor_actions: DeviceAction | list[DeviceAction]):
        if isinstance(motor_actions, list):
            action = {
                f"{motor_action.device_name}.{motor_action.action_name}": motor_action.get_value()
                for motor_action in motor_actions
            }
        elif isinstance(motor_actions, DeviceAction):
            action = {f"{motor_actions.device_name}.{motor_actions.action_name}": motor_actions.get_value()}
        self.set_robot_action(action)

