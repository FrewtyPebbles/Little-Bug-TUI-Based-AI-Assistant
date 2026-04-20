from dotenv import load_dotenv
load_dotenv()
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Label, Static, ContentSwitcher
from lib.chat_page import ChatPage
from lib.database.engine import SQL_ENGINE, SQLBase
from lib.model_selection import ModelDisplay, ModelSelectionPrompt
from textual.reactive import reactive
import ollama as oll
from lib.agent import Agent
import logging

from lib.session_manager import SessionData

class AppGUI(App):
    TITLE = "Tensor Chat"
    CSS_PATH = "assets/styles.tcss"

    agent:Agent = Agent()

    current_model:reactive[oll.ListResponse.Model | None] = reactive(None)
    
    current_page_stack:reactive[list[str]] = reactive(["model-selector-page"])

    session_data:SessionData | None = None

    def set_model(self, model:oll.ListResponse.Model):
        self.current_model = model

    def __init__(self, driver_class = None, css_path = None, watch_css = False, ansi_color = False):
        SQLBase.metadata.create_all(SQL_ENGINE)
        super().__init__(driver_class, css_path, watch_css, ansi_color)
        self.model_display = ModelDisplay()
        self.agent.app = self


    def watch_current_model(self, model: oll.ListResponse.Model) -> None:
        """This runs automatically whenever current_model is changed."""
        self.model_display.model_name = model.model if model else "?"

    def push_page(self, page_id: str):
        # Create a NEW list to trigger the watcher
        self.current_page_stack = [*self.current_page_stack, page_id]

    def set_page(self, page_id: str):
        new_stack = list(self.current_page_stack)
        new_stack[-1] = page_id
        self.current_page_stack = new_stack

    def pop_page(self):
        if len(self.current_page_stack) > 1:
            self.current_page_stack = self.current_page_stack[:-1]
        else:
            self.action_quit()

    
    def watch_current_page_stack(self, stack: list[str]):
        if stack:
            # Tell the switcher to show the ID at the top of the stack
            try:
                self.query_one("#page-switcher", ContentSwitcher).current = stack[-1]
            except:
                pass

    def compose(self) -> ComposeResult:
        yield Header(True)
        with ContentSwitcher(initial="model-selector-page", id="page-switcher"):
            yield ModelSelectionPrompt(self.set_model, id="model-selector-page")
            yield ChatPage(id="chat-page")
        yield self.model_display

if __name__ == "__main__":
    app = AppGUI()
    app.run()
