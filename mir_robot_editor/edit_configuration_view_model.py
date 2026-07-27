
from mir_robot_editor.view_model_base import ViewModelBase, VMAction
from mir_robot.mir_robot_config import mirRobotConfig
from enum import Enum, auto
from PySide6.QtCore import Signal

class EditConfigurationVMAction(Enum):
    APPLY = auto()
    SAVE_AND_CLOSE = auto()
    CANCEL = auto()

class EditConfigurationViewModel(ViewModelBase):
    config_changed = Signal(object)
    closed = Signal()

    def __init__(self, dialog_provider, config: mirRobotConfig):
        super().__init__(dialog_provider)
        self._config = config
        self._config_path = config.path
        self._actions[EditConfigurationVMAction.APPLY] = VMAction("Appliquer", "Appliquer le code JSON à la configuration")
        self._actions[EditConfigurationVMAction.SAVE_AND_CLOSE] = VMAction("Appliquer, enregistrer et fermer", "Appliquer le code JSON à la configuration, l'enregistrer et fermer")
        self._actions[EditConfigurationVMAction.CANCEL] = VMAction("Annuler", "Annuler")
        self._actions[EditConfigurationVMAction.CANCEL].set_enabled(True)

    def _enter_context(self):
        pass
    
    def _exit_context(self, exc_type, exc_value, traceback):
        pass
    
    def get_current_configuration(self) -> mirRobotConfig:
        return self._config

    def get_current_configuration_json(self) -> str:
        return self._config.to_json()

    def on_validation_changed(self, is_valid: bool):
        self._actions[EditConfigurationVMAction.APPLY].set_enabled(is_valid)
        self._actions[EditConfigurationVMAction.SAVE_AND_CLOSE].set_enabled(is_valid)

    def apply(self, new_text:str):
        try:
            self._config = mirRobotConfig.from_json(new_text)
            self._config.path = self._config_path #restaurer le chemin car il est initialisé par from_json
            self.config_changed.emit(self._config)
        except Exception as e:
            self._dialogProvider.warning("Configuration invalide", str(e))

    def save_and_close(self, new_text:str):
        try:
            self._config = mirRobotConfig.from_json(new_text)
            self._config.path = self._config_path
            self.closed.emit()
        except Exception as e:
            self._dialogProvider.warning("Configuration invalide", str(e))

    def cancel(self):
        self.closed.emit()