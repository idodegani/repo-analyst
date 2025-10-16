# Repo Analyst - httpx Repository Q&A Agent

A RAG-based code analysis tool that answers natural language questions about the httpx Python library using semantic search and grounded citations.

## Quick Start (Docker)

```bash
# One-command setup (Linux/Mac)
./quickstart.sh

# One-command setup (Windows PowerShell)
.\quickstart.ps1

# Or manually:
docker-compose up -d
docker-compose run app python app.py query "How does httpx handle SSL certificates?"
```

## Features

- 🔍 **Semantic Search**: Find relevant code using natural language queries
- 📚 **Grounded Answers**: All responses include file:line citations
- 💬 **Conversation History**: Interactive mode maintains context across queries
- ⚡ **Fast Retrieval**: FAISS-powered vector search for quick responses

## Installation

### Option 1: Docker (Recommended)

1. Clone the repository:
```bash
git clone <repository-url>
cd repo-analyst
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

3. Build and run:
```bash
docker-compose up -d
```

### Option 2: Local Installation

1. Clone and set up Python environment:
```bash
git clone <repository-url>
cd repo-analyst
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

4. Build the index:
```bash
python app.py index
```

## Usage

### Command Line Interface

```bash
# Build/rebuild the vector index
python app.py index

# Query the repository
python app.py query "How does httpx validate SSL certificates?"

# Interactive mode with conversation history
python app.py interactive

# Show system information
python app.py info
```

### Example Queries

- "How does httpx handle request timeouts?"
- "Where is proxy support implemented in the code?"
- "What authentication methods are supported?"
- "How does connection pooling work?"
- "What happens when a request exceeds the timeout?"

See `examples.md` for detailed query examples with actual responses.

## Configuration

The system is configured via `config.yaml`:

| Setting | Default | Description |
|---------|---------|-------------|
| `repository.path` | `./httpx` | Path to httpx repository |
| `chunking.chunk_size` | 900 | Characters per chunk |
| `chunking.overlap` | 100 | Overlap between chunks |
| `retrieval.top_k` | 5 | Number of chunks to retrieve |
| `llm.model` | `gpt-4o-mini` | OpenAI model to use |
| `llm.temperature` | 0.1 | Response creativity (0-1) |

## Project Structure

```
repo-analyst/
├── app.py              # CLI interface
├── config.yaml         # Configuration
├── core/               # Core modules
│   ├── config.py       # Configuration loader
│   ├── loader.py       # File loading
│   ├── chunker.py      # Text chunking
│   ├── indexer.py      # FAISS indexing
│   └── rag.py          # RAG pipeline
├── data/               # Generated data
│   ├── faiss.index     # Vector index
│   └── chunks.jsonl    # Chunk metadata
└── httpx/              # Target repository
```

## Limitations & Assumptions

- **Read-only**: The system only reads the httpx repository, no modifications
- **File types**: Indexes only `.py` and `.md` files
- **Context window**: Limited by LLM context size (~4000 tokens)
- **Semantic search**: May miss exact symbol matches (use grep for precise searches)
- **API dependency**: Requires OpenAI API access

## Requirements

- Python 3.11+
- OpenAI API key
- ~100MB disk space for index
- httpx repository (included)

## Troubleshooting

**Index not found error**
```bash
python app.py index  # Rebuild the index
```

**API key error**
```bash
# Ensure .env contains:
open_ai_api_key=sk-your-key-here
```

**Out of memory**
- Reduce `chunking.chunk_size` in config.yaml
- Decrease `retrieval.top_k` for fewer chunks

## License

MIT License - See LICENSE file for details
