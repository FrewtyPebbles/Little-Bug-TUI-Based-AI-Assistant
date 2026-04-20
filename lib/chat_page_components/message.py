import logging

from plyer import notification
from textual import work
from textual.widgets import Static, Markdown, Label
from textual.reactive import reactive
import datetime
import ollama as oll
from typing import TYPE_CHECKING, Any, AsyncIterator

from lib.utility import repr_tool_args
if TYPE_CHECKING:
    from main import AppGUI

class UserMessage(Static):
    app: "AppGUI"
    def __init__(self, content:str, time:datetime.datetime, **kwargs):
        super().__init__(**kwargs)
        self.content = content
        self.time = time

    def compose(self):
        yield Markdown(self.content)
        yield Label(f"sent {self.time.strftime('%Y-%m-%d %H:%M:%S')}")

class ModelMessage(Static):
    app: "AppGUI"
    content = reactive("")
    time = reactive(None)
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.streaming_response:AsyncIterator[oll.ChatResponse] | None = None

    @work
    async def stream_message(self):
        if not self.streaming_response:
            raise RuntimeError("Attempt to stream message without a streaming_response set.")
        full_content = ""
        thinking = False
        tool_calls_dict:dict[str, oll.Message.ToolCall] = {}
        thinking_text = ""
        async for chunk in self.streaming_response:
            message = chunk.message
            content = message.content
            if message.thinking:
                thinking_text += message.thinking
            elif content:
                full_content += content
                if "<think>" in full_content and "</think>" not in full_content:
                    thinking = True
                if full_content.endswith("</think>"):
                    thinking = False
                if not thinking:
                    self.content += content
            if message.tool_calls:
                for tool in message.tool_calls:
                    idx = tool.get('index', 0)
                    if idx not in tool_calls_dict:
                        tool_calls_dict[idx] = tool
                    else:
                        # If arguments are strings, append them; if dicts, update them
                        incoming_args = tool.function.arguments
                        existing_args = tool_calls_dict[idx].function.arguments
                        
                        if isinstance(incoming_args, str):
                            tool_calls_dict[idx].function.arguments += incoming_args
                        elif isinstance(incoming_args, dict):
                            tool_calls_dict[idx].function.arguments.update(incoming_args)
        
        all_tool_calls = list(tool_calls_dict.values())

        self.app.session_data.append_history({
            "role": "assistant",
            "content": full_content,
            "tool_calls": all_tool_calls
        })

        for tool_call in all_tool_calls:
            # 1. Get the actual function from your local code
            function_name = tool_call.function.name
            args = tool_call.function.arguments
            
            # 2. Execute it (assuming you have a registry of functions)
            result = await self.app.agent.call_tool(function_name, args)

            if function_name != "finish_response_tool":
                self.content += f"\n> Tool: {function_name}\n\narguments:`{repr_tool_args(args)}`\n```\n{result}\n```\n"

            # 3. ADD THIS TO THE CONTEXT
            self.app.session_data.append_history({
                "role": "tool",
                "content": str(result), # The data the model needs
                "name": function_name   # Helps the model link result to request
            })

            if function_name == "finish_response_tool":
                self.time = datetime.datetime.now()
                break
        logging.info(f"MODEL THINKING:\n{thinking_text}")

    def watch_time(self, old_value: datetime.datetime | None, new_value: datetime.datetime | None):
        model_message_time = self.query_one("#model-message-time", Label)
        if model_message_time:
            if new_value:
                model_message_time.update(f"Replied at {new_value.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                model_message_time.update("Writing response...")

    def watch_content(self, old_value: str, new_value: str):
        model_message_content = self.query_one("#model-message-content", Markdown)
        if model_message_content:
            model_message_content.update(new_value)

    def compose(self):
        yield Markdown(id="model-message-content")
        yield Label(f"Writing response...", id="model-message-time")