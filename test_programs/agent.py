from backend.agent import ResponseChunk, ToolCall, ToolResponse
from backend.agent.ollama.agent import OllamaAgent, OllamaStreamResponse
import asyncio
import sys
import time

async def main():
    agent = OllamaAgent("localhost:11434", "qwen3.5:4b", system_prompt="You are an AI assistant. Do not think about your responses.")
    while True:
        stream_response:OllamaStreamResponse = await agent.prompt(input("USER: "))
        print("AGENT:")
        start_time = time.time()
        end_time = None
        async for chunk in stream_response:
            if not chunk.thinking:
                if end_time is None:
                    end_time = time.time()
                    print(f"Thought for {end_time - start_time} seconds...")
                    
                if isinstance(chunk, ResponseChunk):
                    sys.stdout.write(chunk.content)
                if isinstance(chunk, ToolCall):
                    sys.stdout.write(f"\nCalling tool \"{chunk.function_name}\"\n")
                if isinstance(chunk, ToolResponse):
                    sys.stdout.write(f"\nTool response \"{chunk.name}\":\n{chunk.response}\n")
                sys.stdout.flush()
        print()


if __name__ == "__main__":
    asyncio.run(main())