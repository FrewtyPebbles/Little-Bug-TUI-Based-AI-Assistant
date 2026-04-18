from __future__ import annotations
from typing import AsyncIterator, Awaitable, Callable
import ollama as oll
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from main import AppGUI

class SessionData:
    def __init__(self, app:"AppGUI"):
        self.app = app
        self.name = "?"
        self._history:list[dict] = [{"role":"system","content":self.app.agent.current_agent.system_prompt}]

    def append_history(self, history:dict):
        self._history.append(history)


    def pop_history(self):
        self._history.pop()

    def set_history(self, history:dict):
        self._history[-1] = history
    
    def get_history(self) -> list[dict]:
        return self._history

    