from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


@dataclass
class ToolCall:
    id:str
    function_name:str
    arguments:dict[str, Any]

    def __hash__(self):
        return hash(self.function_name)
    
class ToolResponse(ABC):
    def __init__(self, name:str, response:str, id:str = ""):
        self.name = name
        self.response = response
        self.id = id

    def to_dict(self) -> dict:
        res = {
            "type":"ToolResponse",
            "name": self.name,
            "response": self.response,
            "id": self.id
        }

        return res
    
    @classmethod
    def from_dict(cls, dictionary:dict) -> Self:
        return cls(dictionary["name"], dictionary["response"], dictionary["id"])

    @abstractmethod
    @classmethod
    def serialize(cls, instance:"ToolResponse") -> dict:
        """
        This serializes the tool response for the specific llm backend.
        """

class ToolOrigin(Enum):
    Remote = "remote server"
    Client = "client"
    Hybrid = "client and remote server"

class ToolArgument:
    def __init__(self, name:str, arg_type:type, description:str, default:Any|None = None, required:bool = True, validator:Callable = lambda val: True, validation_fail_message:str|None = None) -> None:
        self.name = name
        self.arg_type = arg_type
        self.default = default
        self.description = description
        self.required = required
        self.validator = validator
        self.validation_fail_message = validation_fail_message

    def validate(self, argument_value:Any) -> bool:
        return self.validator(argument_value)

    def __str__(self) -> str:

        required = f"This argument is required." if self.required else "This argument is not required."
        default = f"Defaults to {repr(self.default)}. " if self.default is not None else ""
        
        return f"    {self.name} ({self.arg_type.__name__}): {required} {default}{self.description} "

class Tool:
    def __init__(self, name:str, arguments:list[ToolArgument], description:str, returns:str, handler_callback:Callable, origin:ToolArgument):
        self.description = description
        self.name = name
        self.arguments = {argument.name:argument for argument in arguments}
        self.returns = returns
        self.origin = origin
        self.handler_callback = handler_callback
        self.tool_registry:ToolRegistry|None = None

    def execute(self, **kwargs):
        failure_list = []
        for arg in self.arguments.values():
            if arg.name not in kwargs:
                if arg.required:
                    failure_list.append(f"\"{arg.name}\" is a required argument for the \"{self.name}\" tool.")
                else:
                    kwargs[arg.name] = arg.default
                continue

            is_valid = arg.validate(kwargs[arg.name])
            if not is_valid:
                failure_list.append(arg.validation_fail_message)
                
        
        if failure_list:
            return f"Executing the \"{self.name}\" tool failed for the following reasons: {' '.join(failure_list)}"
        
        return self.handler_callback(**kwargs)

    def __str__(self) -> str:
        arguments = "\n".join([argument for argument in self.arguments])
        return f"""{self.description}

This tool executes on the {self.origin}.

Args:
{arguments}

Returns:
    {self.returns}
"""


class ToolRegistry:
    def __init__(self, tools_list:list[Tool]|None = None):
        tools_list = tools_list if tools_list else []
        self.tools:dict[str, Tool] = {}
        for tool in tools_list:
            tool.tool_registry = self
            self.tools[tool.name] = tool

    def __contains__(self, tool:str) -> bool:
        return tool in self.tools

    def __getitem__(self, key:str) -> Tool:
        return self.tools[key]