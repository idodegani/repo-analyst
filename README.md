# Repo Analyst - httpx Repository Q&A Agent

A RAG-based code analysis tool that answers natural language questions about the httpx Python library using semantic search and grounded citations.

## Features

- 🔍 **Semantic Search**: Find relevant code using natural language queries
- 📚 **Grounded Answers**: All responses include file:line citations from actual code
- 🛡️ **Query Router**: Validates query relevance and refines informal queries for better results
- 💬 **Conversation History**: Interactive mode maintains context across queries
- ⚡ **Fast Retrieval**: FAISS-powered vector search for quick responses
- 🎯 **Answer Validation**: LLM judge evaluates answer quality and triggers retries if needed
- 🧠 **Intelligent Chunking**: AST-based parsing for Python code preserves semantic boundaries

## Installation

### Option 1: Docker (Recommended)

Follow these steps to get started:

```bash
# 1. Clone the repository
git clone https://github.com/idodegani/repo-analyst.git
cd repo-analyst

# 2. Ensure Docker Desktop is installed and running
# Download from: https://www.docker.com/products/docker-desktop

# 3. Create .env file with OpenAI API key
echo "open_ai_api_key=sk-proj-YOUR_ACTUAL_KEY" > .env

# 4. Clone the httpx repository (the code to analyze)
git clone https://github.com/encode/httpx.git

# 5. Build and start the Docker container
docker-compose up -d

# 6. Index the repository (creates FAISS embeddings)
docker-compose run --rm app python app.py index

# 7. Run queries (colors work automatically)
docker-compose run --rm app python app.py query "how does httpx handle timeouts?"
```

### Option 2: Local Installation (Less Recommended)

1. Clone and set up Python environment:
```bash
git clone https://github.com/idodegani/repo-analyst.git
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
echo "open_ai_api_key=sk-proj-YOUR_ACTUAL_KEY" > .env
```

4. Clone the httpx repository:
```bash
git clone https://github.com/encode/httpx.git
```

5. Build the index:
```bash
python app.py index
```

## Usage

### Docker Commands (Recommended)

```bash
# Query the repository
docker-compose run --rm app python app.py query "How does httpx validate SSL certificates?"

# Interactive mode with conversation history
docker-compose run --rm app python app.py interactive

# Show help and available commands
docker-compose run --rm app python app.py --help

# Show system information and configuration
docker-compose run --rm app python app.py info

# Rebuild the index (if code changes)
docker-compose run --rm app python app.py index
```

### Local Commands (If using venv)

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

1. **Query Routing**: An LLM router first classifies if your query is relevant to httpx and refines informal queries for better embedding quality
2. **Relevance Check**: Off-topic, toxic, or inappropriate queries receive contextual rejection messages and skip RAG processing
3. **Query Processing**: Refined queries are converted into embeddings using a sentence-transformer model
4. **Semantic Search**: FAISS searches through pre-indexed code chunks to find the most relevant pieces of code
5. **Context Building**: Retrieved code chunks are formatted with file:line citations and combined with conversation history
6. **Answer Generation**: GPT-4o-mini generates an answer based solely on the retrieved context using your original query
7. **Quality Validation**: An LLM judge evaluates the answer's grounding in evidence (scores 1-6)
8. **Retry Logic**: Low-scoring answers trigger regeneration with specific feedback
9. **Citation Verification**: The system ensures all answers include proper file:line references

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

### Router Settings
- `router.enabled`: Enable query relevance classification (default: true)
- `router.model`: LLM model for classification and refinement (default: gpt-4o-mini)
- `router.temperature`: Temperature for routing decisions (default: 0.0)

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
│   ├── router.py       # Query relevance classifier and refiner
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


## Acknowledgments

- Built with LangGraph for pipeline orchestration
- Uses FAISS for efficient vector search
- Powered by OpenAI's GPT models
- Enhanced CLI with Rich library