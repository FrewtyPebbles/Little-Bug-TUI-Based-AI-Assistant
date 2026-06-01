from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterator, Callable, Generic, Iterator, Self, TypeVar
from backend.agent import ToolCall, ToolResponse, ToolRegistry
import asyncio

@dataclass
class ResponseChunk:
    content:str
    tool_calls:list[ToolCall]|None = None
    thinking:bool = False

class BaseStreamResponse(ABC):
    """
    This is an itterator which is a generic streaming response for any of the supported llm backends.
    """
    chunk_queue:asyncio.Queue[ResponseChunk|ToolCall|ToolResponse|None]

    async def get_chunks(self) -> AsyncIterator[ResponseChunk|ToolCall|ToolResponse]:
        while chunk := await self.chunk_queue.get():
            yield chunk

    def __aiter__(self) -> AsyncIterator[ResponseChunk|ToolCall|ToolResponse]:
        res = self.get_chunks()
        asyncio.create_task(self.listen_for_chunks())
        return res

    @abstractmethod
    async def listen_for_chunks(self):
        """
        Internal method which itteratively waits for and gets the next chunk of the llm's response then pushes it to the chunk_queue.
        """

class MessageSender(Enum):
    Agent = 0
    User = 1

class Message(ABC):
    """
    This is a single message in an agent's chat history.
    """
    def __init__(self, content:str, sender:MessageSender, tool_calls:list[ToolCall]|None = None, images:list[bytes]|None = None, thinking:str|None = None):
        self.content = content
        self.sender = sender
        self.tool_calls = tool_calls if tool_calls else []
        self.images = images if images else []
        self.thinking = thinking

    def to_dict(self) -> dict:
        res = {
            "type":"Message",
            "content":self.content,
            "sender":self.sender
        }

        tool_calls = []

        for tool_call in self.tool_calls:
            tool_calls.append({
                "id":tool_call.id,
                "function_name":tool_call.function_name,
                "arguments":tool_call.arguments
            })

        res["tool_calls"] = tool_calls
        res["images"] = self.images
        res["thinking"] = self.thinking

        return res
    
    @classmethod
    def from_dict(cls, dictionary:dict) -> Self:
        tool_calls = []

        if "tool_calls" in dictionary:
            for tool_call in dictionary["tool_calls"]:
                tool_calls.append(ToolCall(tool_call["id"], tool_call["function_name"], tool_call["arguments"]))

        return cls(dictionary["content"], dictionary["sender"], tool_calls, dictionary["images"], dictionary["thinking"])

    @classmethod
    @abstractmethod
    def serialize(cls, instance:"Message") -> dict:
        """
        This method converts the message to the schema that the llm backend uses.
        It is a class method so our instance does not influence which serialize method gets called.
        """
        
MessageHistorySerialized = TypeVar('MessageHistoryTemplateType')
class BaseChatHistory(ABC, Generic[MessageHistorySerialized]):

    def __init__(self, system_prompt:str = "", history:list[Message|ToolResponse]|None = None):
        self.system_prompt = system_prompt
        self.history = history if history else []
    
    def append(self, artifact:Message|ToolResponse):
        self.history.append(artifact)

    @classmethod
    def from_dict(cls, data:dict) -> Self:
        """
        Create the chat history from a dictionary.
        
        SCHEMA:
        ```python
        {
            "system_prompt":str,
            "history": [
                Message.to_dict() | ToolResponse.to_dict(), ...
            ]
        }
        ```
        """
        history = []
        for artifact in data["history"]:
            if artifact["type"] == "ToolResponse":
                history.append(ToolResponse.from_dict(artifact))
            if artifact["type"] == "Message":
                history.append(Message.from_dict(artifact))
        return cls(system_prompt=data["system_prompt"], history=history)


    @abstractmethod
    def serialize(self) -> MessageHistorySerialized:
        """
        Returns the type of chat history native to that llm backend
        """

class BaseAgent(ABC):
    """
    This is the class used to connect to and query the agent.  It keeps track of chat history, handles tool calling, and is highly modular.
    """
    tools:ToolRegistry
    """
    Stores the centralized remote and client side tools.
    """
    history:BaseChatHistory
    """
    This stores the state of the chat history.
    """

    @abstractmethod
    async def prompt(self, content:str, images:list[bytes]|None = None) -> BaseStreamResponse:
        """
        Returns a stream response for the given prompt.
        """
        # serialize chat history here and inject into prompt
        # The chat history is re-serialized every prompt in case the system prompt is modified or something or other.
        # ^ this is kind of an experiment