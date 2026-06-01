from typing import Any, AsyncIterator

from backend.agent import BaseAgent, Message, MessageSender, ToolResponse, BaseChatHistory, BaseStreamResponse, ResponseChunk
import json
import ollama

from backend.agent import ToolCall

class OllamaMessage(Message):
    @classmethod
    def serialize(cls, instance:Message) -> dict:
        res = {
            "role": "user" if instance.sender == MessageSender.User else "assistant",
            "content": instance.content,
        }
        if instance.images:
            res["images"] = instance.images

        if instance.tool_calls:
            msg_tool_calls = []
            for tool_call in instance.tool_calls:
                msg_tool_calls.append({
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function_name,
                        "arguments": json.dumps(tool_call.arguments)
                    }
                })
            res["tool_calls"] = msg_tool_calls
        
        return res
    
class OllamaToolResponse(ToolResponse):
    @classmethod
    def serialize(cls, instance:ToolResponse):
        return {
            "role":"tool",
            "tool_call_id":instance.id,
            "name":instance.name,
            "content":instance.response
        }
    
class OllamaChatHistory(BaseChatHistory[list[dict[str, Any]]]):
    def serialize(self) -> list[dict[str, Any]]:
        serialized_history = [{
            "role":"system",
            "content":self.system_prompt
        }]
        for artifact in self.history:
            if isinstance(artifact, Message):
                serialized_history.append(OllamaMessage.serialize(artifact))
            if isinstance(artifact, ToolResponse):
                serialized_history.append(OllamaToolResponse.serialize(artifact))

        return serialized_history

class OllamaStreamResponse(BaseStreamResponse):
    def __init__(self, raw_streaming_response:AsyncIterator[ollama.ChatResponse], agent:"OllamaAgent"):
        self.raw_streaming_response = raw_streaming_response
        self.agent = agent

    async def listen_for_chunks(self):
        thinking = None
        content = ""
        tool_calls_accumulator = {}
        async for raw_chunk in self.raw_streaming_response:
            message = raw_chunk.get("message", {})
            if "thinking" in message and message["thinking"]:
                thinking_chunk = message['thinking']
                if not thinking:
                    thinking = thinking_chunk
                else:
                    thinking += thinking_chunk
                self.chunk_queue.put(ResponseChunk(thinking=True, content=thinking_chunk))
                continue
            
            content_chunk = ""
            if 'content' in message and message['content']:
                content_chunk = message['content']
                content += content_chunk
                self.chunk_queue.put(ResponseChunk(content=content_chunk))

            if 'tool_calls' in message and message['tool_calls']:
                for tool_call in message['tool_calls']:
                    index = tool_call.get('index', 0) # Track multi-tool execution index
                    
                    if index not in tool_calls_accumulator:
                        tool_calls_accumulator[index] = {
                            "id": tool_call.get("id", ""),
                            "name": tool_call.get("function", {}).get("name", ""),
                            "arguments": ""
                        }
                    
                    # Accumulate incoming JSON argument string fragments
                    arg_fragment = tool_call.get("function", {}).get("arguments", "")
                    tool_calls_accumulator[index]["arguments"] += arg_fragment
        
        for _, tool in tool_calls_accumulator.items():
            tool_name = tool["name"]
            tool_id = tool["id"]
            tool_args = json.loads(tool["arguments"])

            tool_call = ToolCall(tool_id, tool_name, tool_args)
            self.chunk_queue.put(tool_call)
            self.agent.history.append(tool_call)
            if tool_name in self.agent.tools:
                result = self.agent.tools[tool_call.function_name].execute(**tool_call.arguments)
                tool_response = ToolResponse(tool_name, result, tool_id)
                self.chunk_queue.put(tool_response)
                self.agent.history.append(tool_response)
            else:
                tool_error = f"The tool \"{tool_name}\" is not an existing tool."
                tool_response = ToolResponse(tool_name, tool_error, tool_id)
                self.chunk_queue.put(tool_response)
                self.agent.history.append(tool_response)

        self.chunk_queue.put(None)

class OllamaAgent(BaseAgent):
    def __init__(self, host:str, model:str, history:dict|None = None, system_prompt:str = ""):
        self.client = ollama.AsyncClient(host)
        self.model = model
        if history:
            self.history = OllamaChatHistory.from_dict(history)
        else:
            self.history = OllamaChatHistory(system_prompt)
        
    async def prompt(self, content:str, images:list[bytes]|None = None) -> OllamaStreamResponse:
        raw_streaming_response = await self.client.chat(
            model=self.model,
            messages=self.history.serialize(),
            stream=True
        )
        return OllamaStreamResponse(raw_streaming_response, self)