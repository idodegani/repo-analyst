"""Document indexing module.

This module handles embedding generation and FAISS index creation.
"""

import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from pathlib import Path
from typing import List, Dict

from .config import Config
from .loader import RepositoryLoader
from .chunker import CodeChunker


class DocumentIndexer:
    """Indexes code repository chunks into a FAISS vector store.
    
    This class orchestrates the full indexing pipeline:
    1. Load files from repository
    2. Chunk files into semantic units
    3. Generate embeddings for chunks
    4. Build FAISS index
    5. Save metadata
    """
    
    def __init__(self, config: Config):
        """Initialize the document indexer.
        
        Args:
            config: Config object with indexing settings
        """
        self.config = config
        self.model = SentenceTransformer(
            config.get('vector_store', 'embedding_model')
        )
        self.chunks: List[Dict] = []
        self.embeddings: np.ndarray = np.array([])
    
    def index_repository(self) -> None:
        """Execute the full indexing pipeline.
        
        This method:
        1. Discovers and loads repository files
        2. Chunks files into semantic units
        3. Generates embeddings
        4. Builds FAISS index
        5. Saves metadata to JSONL
        """
        print("Starting indexing...")
        
        # 1. Load files
        loader = RepositoryLoader(self.config)
        files = loader.discover_files()
        
        # 2. Chunk files
        chunker = CodeChunker(self.config)
        for file_path in files:
            content = loader.load_file(file_path)
            if content:
                file_chunks = chunker.chunk_file(content, str(file_path))
                self.chunks.extend(file_chunks)
        
        print(f"Created {len(self.chunks)} chunks")
        
        if not self.chunks:
            print("Warning: No chunks created. Check your repository path and file extensions.")
            return
        
        # 3. Generate embeddings
        self._generate_embeddings()
        
        # 4. Build FAISS index
        self._build_faiss_index()
        
        # 5. Save metadata
        self._save_metadata()
        
        print("Indexing complete!")
    
    def _generate_embeddings(self) -> None:
        """Generate embeddings in batches.
        
        Processes chunks in batches for memory efficiency and shows
        progress during generation.
        """
        texts = [chunk['text'] for chunk in self.chunks]
        print(f"Generating embeddings for {len(texts)} chunks...")
        
        batch_size = 32
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = self.model.encode(batch, show_progress_bar=True)
            all_embeddings.extend(batch_embeddings)
        
        self.embeddings = np.array(all_embeddings).astype('float32')
        print(f"Generated embeddings: {self.embeddings.shape}")
    
    def _build_faiss_index(self) -> None:
        """Build FAISS index with cosine similarity.
        
        Uses IndexFlatIP (inner product) with L2-normalized vectors
        to achieve cosine similarity search.
        """
        # Normalize for cosine similarity
        faiss.normalize_L2(self.embeddings)
        
        # Create index (IndexFlatIP for cosine with normalized vectors)
        dimension = self.embeddings.shape[1]
        index = faiss.IndexFlatIP(dimension)
        index.add(self.embeddings)
        
        # Save index
        index_path = self.config.get('vector_store', 'index_path')
        Path(index_path).parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, index_path)
        print(f"Saved FAISS index: {index.ntotal} vectors")
    
    def _save_metadata(self) -> None:
        """Save chunk metadata to JSONL.
        
        Each line contains a JSON object with chunk information:
        - text: The chunk content
        - file_path: Source file path
        - start_line: Starting line number
        - end_line: Ending line number
        - type: Chunk type (FunctionDef, ClassDef, markdown, etc.)
        """
        metadata_path = self.config.get('vector_store', 'metadata_path')
        Path(metadata_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            for chunk in self.chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + '\n')
        print(f"Saved metadata: {len(self.chunks)} chunks")
