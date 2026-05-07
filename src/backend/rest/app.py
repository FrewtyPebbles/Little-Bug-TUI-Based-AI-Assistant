from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from backend.mcp.app import MCP
from fastmcp.utilities.lifespan import combine_lifespans

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    print("Starting up the app...")
    yield
    print("Shutting down the app...")

MCP_APP = MCP.http_app(path="/")

APP = FastAPI(lifespan=combine_lifespans(app_lifespan, MCP_APP.lifespan))
APP.mount("/mcp", MCP_APP)