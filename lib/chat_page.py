from types import CoroutineType
from typing import AsyncIterator
from textual import events, on, work
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widgets import Header, Footer, Label, OptionList, Static, Button, TextArea, Markdown
from textual.widgets.option_list import Option
from textual.containers import VerticalScroll
from textual.worker import Worker
from lib.chat_page_components.message import UserMessage, ModelMessage
import ollama as oll
from typing import Any, Callable, TYPE_CHECKING
from lib.session_manager import SessionData
import datetime
if TYPE_CHECKING:
    from main import AppGUI

class ChatInput(TextArea):
    """A TextArea that submits on Enter instead of adding a newline."""
    async def _on_key(self, event: events.Key) -> None:
        if event.key == "enter" and not event.key == "shift+enter":
            event.prevent_default()
            event.stop()
            
            prompt = self.text.strip()
            if prompt:
                self.text = ""
                self.screen.query_one(ChatPage).send_prompt(prompt)
        if event.key == "shift+enter":
            event.prevent_default()
            event.stop()
            self.insert("\n")

class ChatPage(Static):
    app:"AppGUI"
    current_stream: Worker[None] | None = None
    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="chat-history")
        yield ChatInput(placeholder="Type your prompt here.", id="prompt-box")
        yield Label("?", id="chat-topic")

    def on_show(self) -> None:
        self.query_one("#prompt-box").focus()

    async def append_user_message(self, message: dict):
        # Use .update() to refresh the visual label
        chat_history_container = self.query_one("#chat-history", VerticalScroll)
        await chat_history_container.mount(UserMessage(message["content"], datetime.datetime.now()))
        self.app.session_data.append_history(message)

    @work
    async def send_prompt(self, prompt:str):
        if self.current_stream:
            await self.current_stream.wait()

        topic_response_cort: None | CoroutineType[Any, Any, oll.GenerateResponse] = None
        if not self.app.session_data:
            topic_response_cort = self.app.agent.oll_client.generate(self.app.current_model.model, f"Generate a descriptive title and nothing else for a text chat based on the following prompt: {prompt}",
                think=False,
                options={
                    'think': False
                }
            )
            self.app.session_data = SessionData(self.app)
        

        await self.append_user_message({'role': 'user', 'content': prompt})
        
        if topic_response_cort != None:
            topic_response = await topic_response_cort
            self.app.session_data.name = topic_response.response
            self.query_one("#chat-topic", Label).update(topic_response.response)

        await self.app.agent.prompt()

