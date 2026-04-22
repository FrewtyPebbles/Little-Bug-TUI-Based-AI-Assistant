# Little Bug 🐛

A local-first, terminal-based AI assistant built with Ollama and Textual. Interact with local AI models securely from your terminal.

## 🌟 Features

- **Local-First**: All AI processing happens locally on your machine
- **Multiple Models**: Switch between different Ollama models seamlessly
- **Streaming Responses**: Real-time chat updates as the model generates text
- **Tool Support**: Function calling for enhanced capabilities
- **Vector Embeddings**: RAG (Retrieval-Augmented Generation) support via SQLite-Vec

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----|
| UI Framework | [Textual](https://github.com/Textualize/textual) |
| Web Framework | [FastAPI](https://fastapi.tiangolo.com/) |
| Database | SQLite + SQLAlchemy |
| Vector Store | SQLite-Vec |
| AI Engine | [Ollama](https://ollama.com/) |
| Async | asyncio + httpx |

## 📦 Installation

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com/) installed and running
- `uv` package manager (recommended) or `pip`

### Quick Start

```bash
# Clone or navigate to the project
cd TUI-Based-AI-Assistant

# Install dependencies using uv (fastest)
uv sync

# Run the TUI client
littlebug

# Or run the API server
littlebug-server