from typing import Callable, Generic, List
from typing_extensions import ParamSpec

P = ParamSpec("P")
Handler = Callable[P, None]
class Event_(Generic[P]):
    def __init__(self) -> None:
        self._handlers: List[Handler] = []

    def subscribe(self, handler: Handler) -> None:
        self._handlers.append(handler)

    def unsubscribe(self, handler: Handler) -> None:
        self._handlers.remove(handler)

    def fire(self, *args: P.args, **kwargs: P.kwargs) -> None:
        for handler in self._handlers:
            handler(*args, **kwargs)