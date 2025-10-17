# Repo Analyst - httpx Repository Q&A Agent

A RAG-based code analysis tool that answers natural language questions about the httpx Python library using semantic search and grounded citations.

## Features

- 🔍 **Semantic Search**: Find relevant code using natural language queries
- 📚 **Grounded Answers**: All responses include file:line citations from actual code
- 💬 **Conversation History**: Interactive mode maintains context across queries
- ⚡ **Fast Retrieval**: FAISS-powered vector search for quick responses
- 🎯 **Answer Validation**: LLM judge evaluates answer quality and triggers retries if needed
- 🧠 **Intelligent Chunking**: AST-based parsing for Python code preserves semantic boundaries

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

# Show system information and configuration
python app.py info
```

### Interactive Mode Commands

- `exit`, `quit`, `q` - Exit interactive mode
- `clear` - Clear conversation history
- `history` - Show conversation history
- `help` - Display available commands

### Example Queries

- "How does httpx handle request timeouts?"
- "Where is proxy support implemented in the code?"
- "What authentication methods are supported?"
- "How does connection pooling work?"
- "What happens when a request exceeds the timeout?"
- "Show me how httpx implements retry logic"
- "Where are HTTP headers validated?"

See `examples.md` for detailed query examples with actual responses.

## How It Works

The system implements a sophisticated RAG pipeline that processes your questions through multiple stages:

1. **Query Processing**: Your natural language question is converted into embeddings using a sentence-transformer model
2. **Semantic Search**: FAISS searches through pre-indexed code chunks to find the most relevant pieces of code
3. **Context Building**: Retrieved code chunks are formatted with file:line citations and combined with conversation history
4. **Answer Generation**: GPT-4o-mini generates an answer based solely on the retrieved context
5. **Quality Validation**: An LLM judge evaluates the answer's grounding in evidence (scores 1-6)
6. **Retry Logic**: Low-scoring answers trigger regeneration with specific feedback
7. **Citation Verification**: The system ensures all answers include proper file:line references

## Configuration

The system is configured via `config.yaml`:

### Repository Settings
- `repository.path`: Path to httpx repository (default: `./httpx`)
- `repository.file_extensions`: File types to index (`.py`, `.md`)
- `repository.exclude_dirs`: Directories to skip (tests, __pycache__, etc.)

### Chunking Parameters
- `chunking.chunk_size`: Characters per chunk (default: 900)
- `chunking.overlap`: Overlap between chunks (default: 100)

### Retrieval Settings
- `retrieval.top_k`: Number of chunks to retrieve (default: 5)
- `retrieval.min_score`: Minimum similarity threshold (default: 0.3)

### LLM Configuration
- `llm.model`: OpenAI model to use (default: `gpt-4o-mini`)
- `llm.temperature`: Response creativity 0-1 (default: 0.1)
- `llm.max_tokens`: Maximum response length (default: 1500)

### Judge Settings
- `judge.enabled`: Enable answer quality evaluation (default: true)
- `judge.max_retries`: Retry attempts for low scores (default: 1)
- `judge.confidence_thresholds`: Score thresholds for confidence levels

### Conversation Settings
- `conversation.enable_history`: Maintain context across queries (default: true)
- `conversation.max_history_turns`: History turns to keep (default: 5)

## Project Structure

```
repo-analyst/
├── app.py              # CLI interface and commands
├── config.yaml         # System configuration
├── core/               # Core RAG modules
│   ├── config.py       # Configuration loader and validator
│   ├── loader.py       # Repository file discovery and loading
│   ├── chunker.py      # AST-based code chunking
│   ├── indexer.py      # FAISS index builder
│   ├── rag.py          # LangGraph RAG pipeline
│   └── judge.py        # LLM answer quality judge
├── data/               # Generated indexes
│   ├── faiss.index     # Vector embeddings index
│   └── chunks.jsonl    # Chunk metadata
├── httpx/              # Target repository (httpx source)
├── Dockerfile          # Multi-stage Docker build
├── docker-compose.yml  # Container orchestration
└── examples.md         # Example queries and responses
```

## System Requirements

- **Python**: 3.11 or higher
- **Memory**: 512MB minimum (200MB typical usage)
- **Disk Space**: 100MB for index and dependencies
- **API Access**: OpenAI API key required
- **OS**: Linux, macOS, or Windows

## Performance

- **Indexing Speed**: ~30 seconds for full httpx repository
- **Query Response**: 1-3 seconds per query
- **Index Size**: ~10MB on disk
- **Concurrent Users**: Single-user design (extend for multi-user)

## Troubleshooting

### Index not found error
```bash
python app.py index  # Rebuild the index
```

### API key error
Ensure your `.env` file contains:
```
open_ai_api_key=sk-your-key-here
```

### Out of memory during indexing
- Reduce `chunking.chunk_size` in config.yaml
- Decrease batch size in indexer.py

### Poor answer quality
- Increase `retrieval.top_k` for more context
- Ensure `judge.enabled` is true for quality control
- Check that your queries are specific and clear

### Slow performance
- Use Docker for optimized dependencies
- Consider using a smaller embedding model
- Reduce `retrieval.top_k` if too high

## Advanced Features

### LLM Judge System
The system includes an intelligent judge that evaluates every answer on a scale of 1-6 based on how well it's grounded in the retrieved evidence. Scores of 1-2 trigger automatic retry with feedback, scores of 3-4 include confidence warnings, and scores of 5-6 indicate well-grounded answers.

### Conversation History
In interactive mode, the system maintains context across queries, allowing follow-up questions that reference previous answers. History is limited to the last 5 turns by default to maintain relevance.

### AST-Based Chunking
Python files are parsed using Abstract Syntax Tree (AST) analysis to extract semantic units like functions and classes, preserving logical boundaries and improving retrieval accuracy.

## Limitations

- **Context Window**: Limited to ~4000 tokens per query due to LLM constraints
- **File Types**: Currently indexes only Python and Markdown files
- **Single Repository**: Analyzes one repository at a time
- **Language Support**: AST parsing only for Python; other languages use simple chunking
- **Real-time Updates**: Requires re-indexing to reflect code changes
- **Semantic Search**: May miss exact symbol matches (use grep for precise searches)

## Contributing

Contributions are welcome! Areas for improvement include:

- Support for additional programming languages
- Integration with more LLM providers
- Hybrid search combining semantic and keyword matching
- Multi-repository support
- Real-time index updates
- Web UI interface

## License

MIT License - See LICENSE file for details

## Acknowledgments

- Built with LangGraph for pipeline orchestration
- Uses FAISS for efficient vector search
- Powered by OpenAI's GPT models
- Enhanced CLI with Rich library