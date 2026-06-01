# This is a chat session between multiple users
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field
from beanie import Document, Indexed, Link

class MessageTextComponent(BaseModel):
    type: Literal["text"] = "text"
    text: str

class MessageImageComponent(BaseModel):
    type: Literal["image"] = "image"
    url: str
    alt_text: str | None = None

class MessageClientToolCallComponent(BaseModel):
    type: Literal["client_tool_call"] = "client_tool_call"
    tool_name: str
    arguments: list[Any]
    result: str

class MessageServerToolCallComponent(BaseModel):
    type: Literal["server_tool_call"] = "server_tool_call"
    tool_name: str
    arguments: list[Any]
    result: str

MessageComponent = Annotated[
    Union[
        MessageTextComponent, 
        MessageClientToolCallComponent, 
        MessageServerToolCallComponent,
        MessageImageComponent  # Don't forget the image component you defined!
    ],
    Field(discriminator="type") # Fast, explicit lookups
]

class UserMessage(Document):
    user_id: int
    author_role: str
    content: list[MessageComponent]
    class Settings:
        name = "user_chat_message"

class SessionSettings(BaseModel):
    type: Literal["settings"] = "settings"
    agent:str
    name:str

class UserSession(Document):
    user_id: int
    session_settings: SessionSettings
    history: list[Link[UserMessage]]
    class Settings:
        name = "user_chat_session"
        on_cascade_delete = "DELETE"
