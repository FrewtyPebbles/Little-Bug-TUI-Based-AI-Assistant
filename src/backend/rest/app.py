from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from backend.relational_database.engine import SQL_ENGINE, SQLBase
from backend.mcp.app import MCP
from fastmcp.utilities.lifespan import combine_lifespans
from backend.rest.routes import ai_chat

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    print("Starting up the app...")
    print("Ensuring SQL Database...")
    SQLBase.metadata.create_all(SQL_ENGINE)
    yield
    print("Shutting down the app...")

MCP_APP = MCP.http_app(path="/")

APP = FastAPI(lifespan=combine_lifespans(app_lifespan, MCP_APP.lifespan))
APP.mount("/mcp", MCP_APP)
APP.include_router(ai_chat.ROUTE)