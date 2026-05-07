from sentence_transformers import SentenceTransformer

from backend.rest.app import APP
from fastmcp import FastMCP


MCP = FastMCP("ai_tools")
EMBEDDINGS_MODEL = SentenceTransformer('all-MiniLM-L6-v2')