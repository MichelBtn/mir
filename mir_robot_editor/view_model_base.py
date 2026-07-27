from PySide6.QtCore import QObject
from mir_utils.ui.dialogs import IDialogProvider
from PySide6.QtCore import Signal
from enum import Enum
from typing import TypeVar, Generic

TAction = TypeVar("TAction", bound=Enum)

class VMAction(QObject):
    action_state_changed = Signal(bool)

    def __init__(self, name:str, description:str, enabled:bool = False):
        super().__init__()
        self.name = name
        self.description = description
        self.enabled = enabled

    def set_enabled(self, enabled: bool):
        if self.enabled == enabled:
            return
        self.enabled = enabled
        self.action_state_changed.emit(enabled)
        
class ViewModelBase(QObject, Generic[TAction]):
    def __init__(self, dialogProvider: IDialogProvider):
        super().__init__()
        self._initialized = False
        self._dialogProvider = dialogProvider
        self._actions: dict[TAction, VMAction] = {}

    def get_action(self, action: TAction) -> VMAction:
        try:
            return self._actions[action]
        except KeyError as e:
            raise KeyError(f"Action non enregistrée: {action}. Exception: {str(e)}") from None

    def __enter__(self):
        self._enter_context()
        self._initialized = True
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._initialized = False
        self._exit_context(exc_type, exc_value, traceback)
        return False #propager une éventuelle exception
    
    def _check_initialized(self):
        if not self._initialized:
            raise RuntimeError(
                "Le ViewModel doit être utilisé via un gestionnaire de contexte ('with')."
            )

    def _enter_context(self):
        """Cette méthode doit être redéfinie dans les classes filles."""
        raise NotImplementedError("Vous devez implémenter cette méthode dans la classe fille.")
    
    def _exit_context(self, exc_type, exc_value, traceback): 
        """Cette méthode doit être redéfinie dans les classes filles."""
        raise NotImplementedError("Vous devez implémenter cette méthode dans la classe fille.")
