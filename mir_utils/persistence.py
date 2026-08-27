
from PySide6.QtCore import QSettings
from typing import Any

class Preferences:
    """Gestionnaire de préférences persistant avec interface dict-like s'appuyant sur QSettings."""

    def __init__(self, application: str, organization: str = "mir"):
        self._settings = QSettings(organization, application)

    def get(self, key: str, default: Any = None) -> Any:
        val = self._settings.value(key, default)
        return val if val is not None else default

    def __getitem__(self, key: str) -> Any:
        if not self._settings.contains(key):
            raise KeyError(key)
        return self._settings.value(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self._settings.setValue(key, value)

    def __contains__(self, key: str) -> bool:
        return self._settings.contains(key)

    def __delitem__(self, key: str) -> None:
        self._settings.remove(key)