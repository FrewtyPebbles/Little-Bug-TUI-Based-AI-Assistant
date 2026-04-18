import asyncio
import logging
import re

import ollama as oll
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable, Literal
from queue import Queue
import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import os
import platform

from textual.containers import VerticalScroll
from lib.agent.command import Shell
from lib.chat_page import ChatPage
from lib.chat_page_components.message import ModelMessage
from lib.session_manager import SessionData
from dataclasses import dataclass
from itertools import islice
if TYPE_CHECKING:
    from main import AppGUI

logging.basicConfig(
    filename='.logs/agent.log', 
    filemode='w', 
    level=logging.INFO,
    format='AGENT[%(asctime)s | %(name)s | %(levelname)s] - %(message)s'
)

def get_file_type(file:Path):
    file_type = "?"
    if file.is_dir():
        file_type = "folder"
    if file.is_file():
        file_type = "file"
    elif file.is_symlink():
        file_type = "symlink"
    elif file.is_socket():
        file_type = "socket"
    elif file.is_fifo():
        file_type = "FIFO/named pipe"
    elif file.is_block_device():
        file_type = "block device"
    elif file.is_char_device():
        file_type = "character device"
    
    return file_type

@dataclass
class AgentType:
    name:str
    tools:list[Callable]
    system_prompt:str

class Agent:
    app:"AppGUI"
    def __init__(self):
        self.oll_client = oll.AsyncClient()
        self.shell = Shell()
        self.finished_response = False
        self.agents = {
            "Assistant":AgentType(
                "Assistant",
                [
                    self.request_command,
                    self.run_command,
                    self.get_datetime,
                    self.get_operating_system,
                    self.list_items_in_directory,
                    self.get_current_working_directory_path,
                    self.read_file,
                    self.finish_response_tool,
                ],
                Path(r"agent_system_prompts\Assistant.md").read_text()
            ),
            "SWE Assistant":AgentType(
                "SWE Assistant",
                [
                    self.request_command,
                    self.run_command,
                    self.get_datetime,
                    self.get_operating_system,
                    self.list_items_in_directory,
                    self.get_current_working_directory_path,
                    self.read_file,
                    self.finish_response_tool,
                ],
                Path(r"agent_system_prompts\SWE Assistant.md").read_text()
            )
        }
        self.current_agent = self.agents["Assistant"]


    def set_agent_type(self, agent_name:str):
        self.current_agent = self.agents[agent_name]
        self.app.session_data._history[0] = {"role":"system","content":self.current_agent.system_prompt}

    def call_tool(self, function_name:str, arguments:dict) -> Any:
        match function_name:
            case "request_command":
                return self.request_command(**arguments)
            case "run_command":
                return self.run_command(**arguments)
            case "get_datetime":
                return self.get_datetime(**arguments)
            case "get_operating_system":
                return self.get_operating_system()
            case "list_items_in_directory":
                return self.list_items_in_directory(**arguments)
            case "get_current_working_directory_path":
                return self.get_current_working_directory_path()
            case "read_file":
                return self.read_file(**arguments)
            case "finish_response_tool":
                return self.finish_response_tool()

    async def prompt(self):
        chat_page = self.app.screen.query_one(ChatPage)
        chat_history_container = chat_page.query_one("#chat-history", VerticalScroll)
        model_message = ModelMessage()
        await chat_history_container.mount(model_message)
        while not self.finished_response:
            history_str = '\n\t'.join([
                f"{chat_item['role']}: {chat_item['content']}" if chat_item['role'] != "tool"
                else f"{chat_item['role']} ({chat_item['name']}): {chat_item['content']}"
                for chat_item in self.app.session_data.get_history()
            ])
            logging.info(f"""Current message history ({datetime.datetime.now().strftime("%d/%m/%Y, %H:%M:%S")}):\n{history_str}""")
            streaming_response:AsyncIterator[oll.ChatResponse] =  await self.oll_client.chat(model=self.app.current_model.model, messages=self.app.session_data.get_history(),
                think=False,
                stream=True,
                tools=self.current_agent.tools,
                options={
                    'think': False
                }
            )


            model_message.streaming_response = streaming_response
            
            chat_page.current_stream = model_message.stream_message()
            
            if chat_page.current_stream:
                await chat_page.current_stream.wait()
                logging.info("Finished message stream.")

        # Reset boolean
        self.finished_response = False
        logging.info("Finished message generation.")

    
    # TOOLS
    async def request_command(self, command:str, command_arguments:list[str|Path]) -> None:
        """
        Request to run a shell command on the user's pc. The command is executed in the format:
        
        {command} {command_arguments[0]} {command_arguments[1]} {command_arguments[...]} {command_arguments[n-1]} {command_arguments[n]}

        Args:
            command: The command/program name.
            command_arguments: The command line interface arguments for the command.
        """
        self.shell.push_command(command, command_arguments)

    async def run_command(self, command:str, command_arguments:list[str|Path]) -> str:
        """
        Run a shell command on the user's pc. The command is executed in the format:
        
        {command} {command_arguments[0]} {command_arguments[1]} {command_arguments[...]} {command_arguments[n-1]} {command_arguments[n]}

        Args:
            command: The command/program name.
            command_arguments: The command line interface arguments for the command.
        """
        self.shell.push_command(command, command_arguments)
        return self.shell.command_queue.get().approve()

    async def get_datetime(self,
    timezone_name: Literal[
        "UTC", 
        "America/New_York", 
        "America/Los_Angeles", 
        "Europe/London", 
        "Europe/Paris", 
        "Asia/Tokyo", 
        "Asia/Dubai", 
        "Australia/Sydney"
    ] | None = None
    ) -> str:
        """
        Request the current date and time for a specific timezone.

        Args:
            timezone_name: The time zone to get the current date and time for. If left as None, it will use the user's time zone. The options are "UTC", "America/New_York", "America/Los_Angeles", "Europe/London", "Europe/Paris", "Asia/Tokyo", "Asia/Dubai", and "Australia/Sydney"
        """
        return datetime.datetime.now(ZoneInfo(timezone_name)).strftime("%d/%m/%Y, %I:%M:%S %p")
    
    def get_operating_system(self) -> str:
        """
        Get the user's current operating system. Possible operating systems include: Windows, Linux, Darwin, and Java.  Other more rare operating systems include: FreeBSD, NetBSD, OpenBSD, SunOS, and AIX.
        If the operating system cannot be determined, the operating system will be unknown.
        """
        operating_system = platform.system()
        return operating_system if operating_system != "" else "unknown"
    
    def get_current_working_directory_path(self) -> str:
        """
        Get the path of the user's terminal's current working directory.
        """
        return f"{Path.cwd()}"
    
    def list_items_in_directory(self, directory:str|Path) -> str:
        # Docstring set elsewhere for formatting purposes
        ret = f"File system items in directory \"{directory}\":\n"
        directory = Path(directory)
        if not directory.exists():
            return f"The file system directory \"{directory}\" does not exist."
        if not directory.is_dir():
            return f"The file system path \"{directory}\" points to a {get_file_type(directory)} not a folder."
        for file in directory.iterdir():
            ret += f" - \"{file.name}\"\n\ttype: {get_file_type(file)}\n"
            if file.is_file():
                line_count = 0
                char_count = 0
                with open('large_file.txt', 'r', encoding='utf-8') as f:
                    for line in f:
                        line_count += 1
                        char_count += len(line)
                ret += f"\tline count: {line_count}\n\tcharacter count: {char_count}\n"
        ret += f"Listed {len([*directory.iterdir()])} file system items in directory."
        return ret
    
    def read_file(self, file_path:str|Path, read_from_line:int = 1, read_from_search:str | None = None, lines_before_target:int = 0, lines:int | None = None) -> str:
        """
        Read part or the entire contents of a file from the user's computer at a specific file system path. You should try to read only what you need to from the file incase it is large.

        Args:
            file_path(type:str|Path): The file system path to the file on the user's computer to read the contents of.
            read_from_line(type:int): This is an integer line number starting from 1 to start reading from. The default value is 1 (the first line).
            read_from_search(type:str|None): If this argument is not None, the tool will read from the first regex match of this string in the file and ignore the value of read_from_line. The default value is None.
            lines_before_target(type:int): This specifies a number of lines to read before the read_from_line or read_from_search line.
            lines(type:int|None): If lines is an integer, this many lines will be read from read_from_target. If lines is None, the whole file will be read from the read_from_line or read_from_search line. The default value is None.
        
        The lines of the file read can be described by the following pseudocode:
        ```
        def tool(file_path, read_from_target, lines_before_target, lines) -> The contents read as a string:
            let read_from_line_number = The line number of read_from_line or from the line number of the first regex match of read_from_search.
            let starting_line = The line number that the tool starts reading from.
            let total_lines = Total lines in the file.

            starting_line = min(max(1, read_from_line_number-lines_before_target), total_lines)
            return read_lines(from=starting_line, to=starting_line + lines)
        ```
        Therefore the tool will read from `starting_line` to `starting_line + lines`.
        For example if arguments read_from_line=10, lines_before_target=3 and lines=4 then the tool will read the file from line 7 to line 10 inclusive.
        """
        error_msg = "Tool error:"
        if not isinstance(file_path, (str, Path)):
            error_msg += f"\nThe `file_path` argument must be either a str or Path not {type(file_path)}."
        if not isinstance(read_from_line, int):
            error_msg += f"\nThe optional argument `read_from_target` argument must be an int not {type(read_from_line)}."
        if not (isinstance(read_from_search, str) or read_from_search == None):
            error_msg += f"\nThe optional argument `read_from_target` argument must be an str or None not {type(read_from_search)}."
        if not isinstance(lines_before_target, int):
            error_msg += f"\nThe optional argument `lines_before_target` argument must be an int not {type(lines_before_target)}."
        if not (isinstance(lines, int) or lines == None):
            error_msg += f"\nThe optional argument `lines` argument must be an int not {type(lines)}."
        
        if error_msg != "Tool error:":
            return error_msg

        file_path = Path(file_path)
        if not file_path.exists():
            return f"The file path \"{file_path}\" does not point to an existing file."
        if not file_path.is_file() and not file_path.is_symlink():
            return f"The file path \"{file_path}\" points to a {get_file_type(file_path)} not a file."

        target_line = read_from_line

        # Find the target line if it's a regex search
        if read_from_search != None:
            with open(file_path, "r") as fp:
                target_line = next((ln for ln, line in enumerate(fp, 1) 
                                    if re.search(read_from_search, line)), None)
            
            if target_line is None:
                return f"Regex pattern not found in file at \"{file_path}\"."

        # Calculate boundaries and read
        start_line = max(1, target_line - lines_before_target)
        
        with open(file_path, "r") as fp:
            content_iter = islice(fp, start_line - 1, (start_line - 1 + lines) if lines else None)
            return "".join(content_iter)

    def finish_response_tool(self) -> None:
        """
        You MUST call this tool when you believe that you have finished fulfilling/answering the user's prompt/request.
        """
        self.finished_response = True

if platform.system().lower() == "windows":
    Agent.list_items_in_directory.__doc__ = """
    List the items inside of a directory at a specific file system path. Each item's type will be listed too. Possible types include file, folder, and symlink. If the item is a file, its line and character count will be listed too.

    Args:
        directory: The string or Path object of the file system path to the directory on the user's system. All of the items inside of this directory will be listed.
    """
else:
    Agent.list_items_in_directory.__doc__ = """
    List the items inside of a directory at a specific file system path. Each item's type will be listed too. Possible types include file, folder, symlink, socket, FIFO/named pipe, block device, and character device. If the item is a file, its line and character count will be listed too.

    Args:
        directory: The string or Path object of the file system path to the directory on the user's system. All of the items inside of this directory will be listed.
    """