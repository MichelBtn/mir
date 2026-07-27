from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, TypeVar
from PySide6.QtCore import QObject, Signal

T = TypeVar("T")

class BackgroundTask(QObject):
    """
    Exécute une fonction bloquante dans un thread du pool, et émet le résultat
    (ou l'exception) via un signal Qt, livré sur le thread GUI.
    """
    finished = Signal(object)   # résultat de la fonction
    failed = Signal(Exception)  # exception levée dans le thread

    def __init__(self, executor: ThreadPoolExecutor, on_finished, on_failed):
        super().__init__()
        self._executor = executor
        self._future: Future | None = None
        self.finished.connect(on_finished)
        self.failed.connect(on_failed)

    def run(self, fn: Callable[[], T]) -> None:
        self._future = self._executor.submit(self._execute, fn)

    def _execute(self, fn: Callable[[], T]) -> None:
        try:
            result = fn()
        except Exception as e:
            self.failed.emit(e)
        else:
            self.finished.emit(result)


class BackgroundWorker:
    """
    Exécute des opérations bloquantes hors du thread GUI, par composition.

    Usage dans un ViewModel :

        class MyViewModel(ViewModelBase):
            def __init__(self, ...):
                super().__init__(...)
                self._worker = BackgroundWorker()

            def do_something(self):
                self._worker.run(self._do_work, self._on_work_finished, self._on_work_failed)

            def _exit_context(self, exc_type, exc_value, traceback):
                self._worker.shutdown()

    Un seul thread est utilisé par défaut (max_workers=1) : les tâches
    soumises s'exécutent toujours séquentiellement, ce qui élimine le
    risque de deadlock d'un pool multi-workers où une tâche attendrait
    une autre tâche qu'elle aurait elle-même soumise au même executor.
    """

    def __init__(self, max_workers: int = 1):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks_in_flight: set[BackgroundTask] = set()

    def run(
        self,
        fn: Callable[[], T],
        on_finished: Callable[[T], None],
        on_failed: Callable[[Exception], None] | None = None,
        guard_flag_owner: object | None = None,
        guard_flag: str | None = None,
    ) -> None:
        """
        Lance fn() dans le thread de fond. on_finished/on_failed sont
        rappelés sur le thread GUI une fois l'opération terminée.

        guard_flag_owner/guard_flag : objet et nom d'attribut bool
        optionnels, mis à True avant le lancement et remis à False après
        on_finished/on_failed. Pratique pour éviter d'empiler des tâches
        identiques (ex: polling). Si l'attribut vaut déjà True, run() ne
        lance rien.
        """
        if guard_flag is not None:
            if getattr(guard_flag_owner, guard_flag, False):
                return
            setattr(guard_flag_owner, guard_flag, True)

        def _wrap(callback):
            def _wrapped(value):
                if guard_flag is not None:
                    setattr(guard_flag_owner, guard_flag, False)
                self._tasks_in_flight.discard(task)
                callback(value)
            return _wrapped

        def _default_failed(error: Exception):
            raise error

        task = BackgroundTask(
            self._executor,
            _wrap(on_finished),
            _wrap(on_failed if on_failed is not None else _default_failed),
        )
        self._tasks_in_flight.add(task)
        task.run(fn)

    def shutdown(self, wait: bool = False):
        self._executor.shutdown(wait=wait)
        self._tasks_in_flight.clear()
