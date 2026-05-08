from sentence_transformers import SentenceTransformer

from backend.rest.app import APP
from fastmcp import FastMCP


MCP = FastMCP("ai_tools")
EMBEDDINGS_MODEL = SentenceTransformer("Qwen/Qwen3-VL-Embedding-2B")