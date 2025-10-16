"""RAG pipeline with LangGraph orchestration.

This module implements the retrieval-augmented generation pipeline
using LangGraph for state management and flow control.
"""

import os
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from typing import List, Dict, TypedDict, Optional

from .config import Config


class RAGState(TypedDict):
    """State for the RAG agent flow.
    
    Attributes:
        query: User's question about the codebase
        query_embedding: Numpy array of the query embedding for FAISS search
        retrieved_chunks: List of relevant code chunks from vector store
        context: Formatted context string to send to LLM
        answer: Final generated answer with citations
        error: Any error message encountered during execution
    """
    query: str
    query_embedding: Optional[np.ndarray]
    retrieved_chunks: List[Dict]
    context: str
    answer: str
    error: Optional[str]


class RAGPipeline:
    """RAG pipeline orchestrated with LangGraph.
    
    This class implements a retrieval-augmented generation pipeline:
    1. Embed query
    2. Retrieve relevant chunks from FAISS
    3. Build context with citations
    4. Generate answer using LLM
    """
    
    def __init__(self, config: Config):
        """Initialize the RAG pipeline.
        
        Args:
            config: Config object with RAG settings
            
        Raises:
            FileNotFoundError: If index or metadata files don't exist
            EnvironmentError: If API key is not set
        """
        self.config = config
        self.model = SentenceTransformer(
            config.get('vector_store', 'embedding_model')
        )
        self.index = None
        self.chunks: List[Dict] = []
        self._load_index_and_metadata()
        
        # Initialize LangChain LLM
        api_key = os.getenv(config.get('llm', 'api_key_env'))
        if not api_key:
            raise EnvironmentError(
                f"Missing environment variable: {config.get('llm', 'api_key_env')}"
            )
        
        self.llm = ChatOpenAI(
            model=config.get('llm', 'model'),
            temperature=config.get('llm', 'temperature'),
            max_tokens=config.get('llm', 'max_tokens'),
            api_key=api_key
        )
        
        # Build LangGraph
        self.graph = self._build_graph()
    
    def _load_index_and_metadata(self) -> None:
        """Load FAISS index and chunk metadata.
        
        Raises:
            FileNotFoundError: If index or metadata files don't exist
        """
        index_path = self.config.get('vector_store', 'index_path')
        metadata_path = self.config.get('vector_store', 'metadata_path')
        
        # Load FAISS index
        try:
            self.index = faiss.read_index(index_path)
            print(f"Loaded FAISS index: {self.index.ntotal} vectors")
        except Exception as e:
            raise FileNotFoundError(
                f"Could not load FAISS index from {index_path}. "
                f"Run indexing first. Error: {e}"
            )
        
        # Load chunks
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                for line in f:
                    self.chunks.append(json.loads(line.strip()))
            print(f"Loaded {len(self.chunks)} chunks")
        except Exception as e:
            raise FileNotFoundError(
                f"Could not load metadata from {metadata_path}. "
                f"Run indexing first. Error: {e}"
            )
    
    def _embed_query(self, state: RAGState) -> RAGState:
        """Node: Generate embedding for the query.
        
        Args:
            state: Current RAG state
            
        Returns:
            Updated state with query_embedding or error
        """
        try:
            query_embedding = self.model.encode([state['query']], show_progress_bar=False)
            state['query_embedding'] = query_embedding.astype('float32')
        except Exception as e:
            state['error'] = f"Error embedding query: {e}"
        return state
    
    def _retrieve_chunks(self, state: RAGState) -> RAGState:
        """Node: Retrieve relevant chunks from FAISS.
        
        Args:
            state: Current RAG state with query_embedding
            
        Returns:
            Updated state with retrieved_chunks or error
        """
        if state.get('error'):
            return state
        
        try:
            # Normalize for cosine similarity
            query_embedding = state['query_embedding']
            faiss.normalize_L2(query_embedding)
            
            # Search
            top_k = self.config.get('retrieval', 'top_k')
            scores, indices = self.index.search(query_embedding, top_k)
            
            # Get chunks
            results = []
            for idx, score in zip(indices[0], scores[0]):
                if idx < len(self.chunks):
                    chunk = self.chunks[idx].copy()
                    chunk['score'] = float(score)
                    results.append(chunk)
            
            state['retrieved_chunks'] = results
        except Exception as e:
            state['error'] = f"Error retrieving chunks: {e}"
        
        return state
    
    def _build_context(self, state: RAGState) -> RAGState:
        """Node: Format retrieved chunks into context.
        
        Args:
            state: Current RAG state with retrieved_chunks
            
        Returns:
            Updated state with context prompt or error
        """
        if state.get('error'):
            return state
        
        try:
            chunks = state['retrieved_chunks']
            
            if not chunks:
                state['error'] = "No relevant information found in the repository."
                return state
            
            # Format context with file:line citations
            context_parts = []
            for i, chunk in enumerate(chunks):
                file_path = chunk['file_path']
                start_line = chunk.get('start_line', '?')
                end_line = chunk.get('end_line', '?')
                citation = f"[{file_path}:{start_line}-{end_line}]"
                
                context_parts.append(
                    f"[Chunk {i+1}] {citation}\n{chunk['text']}"
                )
            
            context = "\n\n".join(context_parts)
            
            # Build prompt
            prompt = f"""You are a code analysis assistant for the httpx library.
Answer the question using ONLY the provided code chunks.

Code Context:
{context}

Question: {state['query']}

Instructions:
- Answer based ONLY on the code above
- Include specific file:line citations in your answer (e.g., httpx/_client.py:45-67)
- Be concise and accurate
- If the context doesn't contain enough information, say so clearly
- Format: Provide answer, then list citations

Answer:"""
            
            state['context'] = prompt
        except Exception as e:
            state['error'] = f"Error building context: {e}"
        
        return state
    
    def _generate_answer(self, state: RAGState) -> RAGState:
        """Node: Generate answer using LLM.
        
        Args:
            state: Current RAG state with context
            
        Returns:
            Updated state with answer
        """
        if state.get('error'):
            state['answer'] = state['error']
            return state
        
        try:
            messages = [
                {"role": "system", "content": "You are a helpful code analysis assistant."},
                {"role": "user", "content": state['context']}
            ]
            response = self.llm.invoke(messages)
            state['answer'] = response.content
        except Exception as e:
            state['answer'] = f"Error generating answer: {e}"
        
        return state
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow.
        
        Returns:
            Compiled StateGraph ready for execution
        """
        workflow = StateGraph(RAGState)
        
        # Add nodes
        workflow.add_node("embed_query", self._embed_query)
        workflow.add_node("retrieve_chunks", self._retrieve_chunks)
        workflow.add_node("build_context", self._build_context)
        workflow.add_node("generate_answer", self._generate_answer)
        
        # Define edges (linear flow)
        workflow.set_entry_point("embed_query")
        workflow.add_edge("embed_query", "retrieve_chunks")
        workflow.add_edge("retrieve_chunks", "build_context")
        workflow.add_edge("build_context", "generate_answer")
        workflow.add_edge("generate_answer", END)
        
        return workflow.compile()
    
    def query(self, user_query: str) -> str:
        """Execute the RAG pipeline.
        
        Args:
            user_query: User's question about the codebase
            
        Returns:
            Generated answer with citations
        """
        initial_state: RAGState = {
            "query": user_query,
            "query_embedding": None,
            "retrieved_chunks": [],
            "context": "",
            "answer": "",
            "error": None
        }
        
        # Run the graph
        final_state = self.graph.invoke(initial_state)
        
        return final_state['answer']
