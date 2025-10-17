# Architecture Overview

## System Design

The Repo Analyst implements a RAG (Retrieval-Augmented Generation) pipeline for answering natural language questions about code repositories. The system follows a multi-stage flow from document ingestion through semantic search to answer generation with quality validation.

## Core Components

### 1. Document Loader (`core/loader.py`)

The RepositoryLoader discovers and loads files from the target repository. It walks the directory structure, filters files by configured extensions (.py and .md), and excludes specified directories like __pycache__, .git, and tests. The loader handles encoding issues gracefully, attempting UTF-8 first and falling back to Latin-1 when necessary.

### 2. Text Chunker (`core/chunker.py`)

The CodeChunker intelligently splits documents into semantic units. For Python files, it uses AST (Abstract Syntax Tree) parsing to extract functions, classes, and async functions as natural chunks. Each chunk preserves its context with file path and line number metadata. For Markdown files, it uses paragraph-based chunking with overlap. Large functions or classes that exceed the chunk size limit are further split with configurable overlap to maintain context at boundaries.

### 3. Document Indexer (`core/indexer.py`)

The DocumentIndexer orchestrates the full indexing pipeline. It coordinates the loader and chunker to process repository files, generates embeddings using the sentence-transformers/all-MiniLM-L6-v2 model, and builds a FAISS index for similarity search. The indexer processes embeddings in batches for memory efficiency and normalizes vectors for cosine similarity search. All chunk metadata is stored in a JSONL file alongside the FAISS index.

### 4. RAG Pipeline (`core/rag.py`)

The RAGPipeline is the heart of the system, orchestrated using LangGraph for state management. The pipeline executes through these nodes:

- **embed_query**: Generates embeddings for the user's query using the same sentence-transformer model
- **retrieve_chunks**: Performs FAISS similarity search with configurable top-k retrieval and minimum score filtering
- **build_context**: Formats retrieved chunks with file:line citations and incorporates conversation history if enabled
- **generate_answer**: Invokes the configured LLM (GPT-4o-mini by default) to produce an answer grounded in the retrieved context
- **judge_answer**: Optionally evaluates answer quality using an LLM judge that scores responses from 1-6
- **validate_answer**: Checks that answers include proper citations and meet quality requirements
- **finalize_answer**: Adds confidence warnings or retry messages based on judge scores

The pipeline supports retry logic when the judge scores an answer poorly (1-2), attempting to regenerate with feedback. Conversation history is maintained across queries with a configurable maximum of 5 turns.

### 5. Answer Judge (`core/judge.py`)

The AnswerJudge implements an LLM-based evaluation system that scores answers based on how well they are grounded in the retrieved evidence. It formats the chunks and answer for evaluation, invokes a judge LLM (can be different from the main LLM for independence), and parses the response to extract scores and feedback. Scores range from 1 (not grounded) to 6 (perfectly grounded). For scores of 1-2, the system triggers a retry with specific feedback about what needs improvement.

### 6. CLI Interface (`app.py`)

The CLI provides multiple commands for interacting with the system:

- **index**: Builds the FAISS index from the repository
- **query**: Answers a single question with optional verbose mode
- **interactive**: Maintains conversation context across multiple queries
- **info**: Displays system configuration and index statistics

The interface uses Rich for enhanced terminal output with panels, markdown rendering, and progress indicators. In interactive mode, users can manage conversation history, clear context, and see judge scores for each answer.

### 7. Configuration (`core/config.py`)

The Config class loads settings from config.yaml and validates required paths and environment variables. It provides nested key access with defaults and supports separate configuration for indexing, retrieval, validation, conversation history, LLM settings, and judge parameters.

## Data Flow

### Indexing Phase

The indexing flow processes repository files through multiple stages. First, the RepositoryLoader discovers all Python and Markdown files in the configured path. The CodeChunker then splits each file into semantic chunks using AST parsing for Python and paragraph splitting for Markdown. The DocumentIndexer generates embeddings for all chunks using sentence-transformers, builds a FAISS index with L2 normalization for cosine similarity, and saves both the index and chunk metadata to disk.

### Query Phase

The query flow implements a sophisticated retrieval and generation pipeline. The user's query is embedded using the same sentence-transformer model. FAISS performs similarity search to retrieve the top-k most relevant chunks. The pipeline builds a context prompt incorporating retrieved chunks with citations and conversation history. The LLM generates an answer based solely on the provided context. If the judge is enabled, it evaluates the answer quality and may trigger a retry with feedback. The answer undergoes validation to ensure proper citations are included. Finally, the system updates conversation history and returns the grounded answer.

## Design Decisions

### Why FAISS?
FAISS provides optimized C++ implementation for fast similarity search, handles large-scale vector collections efficiently, and operates entirely locally without external dependencies.

### Why Sentence Transformers?
The all-MiniLM-L6-v2 model offers an excellent balance of speed and accuracy, has a small footprint (80MB) suitable for local deployment, and provides fast inference without requiring GPU acceleration.

### Why LangGraph?
LangGraph enables clean separation of pipeline stages with explicit state management, provides flexibility to add validation or routing steps, and offers clear execution flow visualization for debugging.

### Why AST-based Chunking for Python?
AST parsing preserves semantic boundaries of functions and classes, maintains natural code organization, and provides accurate line number tracking for citations.

### Why LLM Judge?
The judge provides objective evaluation of answer grounding, enables automatic retry with specific feedback, and helps maintain consistent answer quality across queries.

## Technology Stack

- **Embeddings**: sentence-transformers/all-MiniLM-L6-v2 for local, fast, high-quality embeddings
- **Vector Store**: FAISS for industry-standard, efficient similarity search
- **LLM**: OpenAI GPT-4o-mini for cost-effective, high-performance generation
- **Orchestration**: LangGraph for state management and clean pipeline flow
- **CLI**: Click for command handling and Rich for enhanced terminal output
- **Configuration**: YAML for human-readable settings management
- **Containerization**: Docker with multi-stage builds for efficient deployment

## Performance Characteristics

- **Indexing Time**: Approximately 30 seconds for the full httpx repository
- **Query Latency**: 1-3 seconds including retrieval, generation, and validation
- **Memory Usage**: Around 200MB with loaded index and model
- **Index Size**: Approximately 10MB on disk for FAISS index and metadata
- **Embedding Dimension**: 384 dimensions (all-MiniLM-L6-v2)
- **Batch Processing**: 32 chunks per batch during indexing

## Extensibility Points

1. **Alternative Embeddings**: Change the embedding model in config.yaml to use different sentence-transformers
2. **Different LLMs**: Swap providers (OpenAI, Anthropic, local models) via configuration
3. **Chunking Strategies**: Extend chunker to support language-specific AST parsing or semantic chunking
4. **Retrieval Methods**: Add hybrid search combining keyword and semantic approaches
5. **Validation Rules**: Extend validation logic to check for specific patterns or requirements
6. **Judge Criteria**: Customize judge prompts and scoring rubrics for domain-specific evaluation
7. **Storage Backends**: Replace FAISS with other vector stores (Pinecone, Weaviate, Chroma)

## Security Considerations

- **Read-only Operations**: System only reads repository files, never modifies them
- **API Key Management**: Keys stored in environment variables, never in code or config
- **Docker Security**: Runs as non-root user with minimal attack surface
- **Input Validation**: Query length limits and sanitization prevent abuse
- **Path Traversal Protection**: File loading restricted to configured repository path

## Limitations

1. **Context Window**: Limited to approximately 4000 tokens per query due to LLM constraints
2. **File Types**: Currently only indexes Python and Markdown files
3. **Single Repository**: Designed for analyzing one repository at a time
4. **Semantic Gaps**: May miss exact symbol matches that keyword search would find
5. **Language Support**: AST parsing only supports Python; other languages use simple chunking
6. **Real-time Updates**: Requires re-indexing to reflect repository changes