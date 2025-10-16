# Architecture Overview

## System Design

The Repo Analyst implements a RAG (Retrieval-Augmented Generation) pipeline for answering natural language questions about code repositories.

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   User      │────>│  CLI (app.py)│────>│   Config    │
│   Query     │     │              │     │  (yaml)     │
└─────────────┘     └──────────────┘     └─────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │  RAG Pipeline│
                    │  (core/rag)  │
                    └──────────────┘
                            │
                ┌───────────┴───────────┐
                ▼                       ▼
        ┌──────────────┐       ┌──────────────┐
        │   Retriever  │       │  Synthesizer │
        │   (FAISS)    │       │   (OpenAI)   │
        └──────────────┘       └──────────────┘
                │                       │
                ▼                       ▼
        ┌──────────────┐       ┌──────────────┐
        │Vector Store  │       │   Generated  │
        │(embeddings)  │       │    Answer    │
        └──────────────┘       └──────────────┘
```

## Core Components

### 1. Document Loader (`core/loader.py`)
- **Purpose**: Reads Python and Markdown files from the httpx repository
- **Design**: Recursive file traversal with configurable exclusions
- **Output**: Raw text content with file metadata

### 2. Text Chunker (`core/chunker.py`)
- **Purpose**: Splits documents into semantic chunks for embedding
- **Strategy**: Character-based chunking with overlap
- **Parameters**: 900 chars per chunk, 100 char overlap
- **Rationale**: Balances context preservation with embedding efficiency

### 3. Document Indexer (`core/indexer.py`)
- **Purpose**: Creates and manages the FAISS vector index
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Storage**: FAISS index + JSONL metadata
- **Design Choice**: Local embeddings for privacy and speed

### 4. RAG Pipeline (`core/rag.py`)
- **Purpose**: Orchestrates retrieval and generation flow
- **State Management**: LangGraph for flow control
- **Components**:
  - Query Processor: Embeds user queries
  - Retriever: Finds top-k similar chunks
  - Context Builder: Formats retrieved chunks
  - Answer Generator: Produces grounded responses
  - Validator: Ensures citations are present

### 5. CLI Interface (`app.py`)
- **Purpose**: User interaction layer
- **Commands**: index, query, interactive, info
- **Features**: Rich terminal output, conversation history

## Data Flow

1. **Indexing Phase**
   ```
   Repository Files → Loader → Chunker → Embedder → FAISS Index
   ```

2. **Query Phase**
   ```
   User Query → Embedding → FAISS Search → Top-K Chunks → 
   Context Formation → LLM Generation → Validated Answer
   ```

## Design Decisions

### Why FAISS?
- **Speed**: Optimized C++ implementation for fast similarity search
- **Scalability**: Handles millions of vectors efficiently
- **Local**: No external dependencies or API calls for search

### Why Sentence Transformers?
- **Quality**: Good balance of speed and accuracy
- **Size**: Small model (80MB) runs locally
- **Performance**: Fast inference without GPU

### Why LangGraph?
- **State Management**: Clean separation of pipeline stages
- **Flexibility**: Easy to add validation or routing steps
- **Debugging**: Clear execution flow visualization

### Why Character-based Chunking?
- **Simplicity**: Works across all file types
- **Consistency**: Predictable chunk sizes
- **Context**: Overlap preserves boundary information

## Technology Stack

| Component | Technology | Justification |
|-----------|------------|---------------|
| Embeddings | sentence-transformers | Local, fast, good quality |
| Vector Store | FAISS | Industry standard, efficient |
| LLM | OpenAI GPT-4o-mini | Cost-effective, good performance |
| Orchestration | LangGraph | State management, clean flow |
| CLI | Click + Rich | Developer-friendly interface |
| Config | YAML | Human-readable, standard format |

## Performance Characteristics

- **Indexing**: ~30 seconds for httpx repository
- **Query Latency**: 1-3 seconds (retrieval + generation)
- **Memory Usage**: ~200MB with loaded index
- **Index Size**: ~10MB on disk

## Extensibility Points

1. **Alternative Embeddings**: Swap embedding model in config
2. **Different LLMs**: Change provider in config (OpenAI, Anthropic, etc.)
3. **Chunking Strategies**: Implement AST-based or function-aware chunking
4. **Retrieval Methods**: Add hybrid search (keyword + semantic)
5. **Validation Rules**: Extend validation logic in RAG pipeline

## Security Considerations

- **Read-only**: No file modifications allowed
- **API Keys**: Environment variables, never in code
- **Docker**: Non-root user, minimal attack surface
- **Input Validation**: Query length limits, sanitization

## Limitations

1. **Context Window**: Limited to ~4000 tokens per query
2. **Semantic Gaps**: May miss exact symbol matches
3. **File Types**: Only Python and Markdown files indexed
4. **Single Repository**: Designed for one repo at a time
