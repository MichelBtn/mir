from mir_utils.ui.widgets import IconFinder
from typing import Generic, TypeVar
from PySide6.QtGui import QAction, QKeySequence
from typing import Callable
from mir_utils.ui.view_model_base import ViewModelBase, TAction
from PySide6.QtWidgets import QToolBar

TViewModel = TypeVar("TViewModel", bound=ViewModelBase)

class ViewBase(Generic[TViewModel, TAction]):
    
    def __init__(self, view_model: TViewModel, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._view_model = view_model
        
    @staticmethod
    def find_icon(icon_name:str):
       return IconFinder.find_icon(icon_name)

    def _icon(self, icon_name:str):
        return ViewBase.find_icon(icon_name)

    def _make_action(self, action_id: TAction, callback:Callable[[], None]|None, icon_name:str="", shortcut:str="", toolbar:QToolBar|None=None) -> QAction :
        # pyrefly: ignore [bad-argument-type]
        action_info = self._view_model.get_action(action_id)
        q_action = QAction(action_info.name)
        q_action.setToolTip(action_info.description)   
        if icon_name != "":
            q_action.setIcon(ViewBase.find_icon(icon_name))
        if shortcut != "":
            q_action.setShortcut(QKeySequence(shortcut))
        q_action.setEnabled(action_info.enabled)
        action_info.action_state_changed.connect(q_action.setEnabled)
        if callback is not None:
            q_action.triggered.connect(callback)
        if toolbar is not None:
            toolbar.addAction(q_action)
        return q_action

