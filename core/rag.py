"""RAG pipeline with LangGraph orchestration.

This module implements the retrieval-augmented generation pipeline
using LangGraph for state management and flow control.
Supports conversation history, adaptive retrieval, and result validation.
"""

import os
import json
import re
import faiss
import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from typing import List, Dict, TypedDict, Optional

from .config import Config
from .judge import AnswerJudge


class ConversationTurn(TypedDict):
    """A single turn in the conversation."""
    query: str
    answer: str


class RAGState(TypedDict):
    """State for the RAG agent flow.
    
    Attributes:
        query: User's current question about the codebase
        conversation_history: List of previous Q&A turns
        query_embedding: Numpy array of the query embedding for FAISS search
        retrieved_chunks: List of relevant code chunks from vector store
        context: Formatted context string to send to LLM
        answer: Final generated answer with citations
        validation_passed: Whether answer passed validation checks
        validation_message: Validation feedback message
        judge_score: Score from LLM judge (1-6)
        judge_feedback: Feedback from judge for retry attempts
        retry_count: Number of retry attempts made
        is_retry: Whether this is a retry attempt
        error: Any error message encountered during execution
    """
    query: str
    conversation_history: List[ConversationTurn]
    query_embedding: Optional[np.ndarray]
    retrieved_chunks: List[Dict]
    context: str
    answer: str
    validation_passed: bool
    validation_message: str
    judge_score: Optional[int]
    judge_feedback: Optional[str]
    retry_count: int
    is_retry: bool
    error: Optional[str]


class RAGPipeline:
    """RAG pipeline orchestrated with LangGraph.
    
    This class implements a retrieval-augmented generation pipeline with:
    - Conversation history support
    - Adaptive retrieval (configurable top_k)
    - Result validation
    - Citation grounding
    
    Flow:
    1. Embed query
    2. Retrieve relevant chunks (adaptive based on config)
    3. Build context with conversation history
    4. Generate answer using LLM
    5. Validate answer quality
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
        
        # Load environment variables from .env file
        load_dotenv()
        
        # Initialize embedding model
        self.model = SentenceTransformer(
            config.get('vector_store', 'embedding_model')
        )
        
        # Load FAISS index and metadata
        self.index = None
        self.chunks: List[Dict] = []
        self._load_index_and_metadata()
        
        # Initialize LangChain LLM
        api_key_env = config.get('llm', 'api_key_env')
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise EnvironmentError(
                f"Missing environment variable: {api_key_env}. "
                f"Please set it in your .env file."
            )
        
        self.llm = ChatOpenAI(
            model=config.get('llm', 'model'),
            temperature=config.get('llm', 'temperature'),
            max_tokens=config.get('llm', 'max_tokens'),
            api_key=api_key
        )
        
        # Initialize judge if enabled
        self.judge = None
        if config.get('judge', 'enabled', default=False):
            self.judge = AnswerJudge(config)
        
        # Build LangGraph
        self.graph = self._build_graph()
        
        # Conversation history (maintained across queries)
        self.conversation_history: List[ConversationTurn] = []
    
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
        """Node: Retrieve relevant chunks from FAISS (adaptive).
        
        Uses configurable top_k and filters by minimum score threshold.
        
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
            
            # Adaptive retrieval: get top_k from config
            top_k = self.config.get('retrieval', 'top_k', default=5)
            min_score = self.config.get('retrieval', 'min_score', default=0.3)
            
            # Search
            scores, indices = self.index.search(query_embedding, top_k)
            
            # Get chunks and filter by minimum score
            results = []
            for idx, score in zip(indices[0], scores[0]):
                if idx < len(self.chunks) and score >= min_score:
                    chunk = self.chunks[idx].copy()
                    chunk['score'] = float(score)
                    results.append(chunk)
            
            state['retrieved_chunks'] = results
            
            # If no results meet threshold, return error
            if not results:
                state['error'] = (
                    f"No relevant information found in the repository "
                    f"(all scores below {min_score} threshold)."
                )
        except Exception as e:
            state['error'] = f"Error retrieving chunks: {e}"
        
        return state
    
    def _build_context(self, state: RAGState) -> RAGState:
        """Node: Format retrieved chunks into context with conversation history.
        
        Args:
            state: Current RAG state with retrieved_chunks and conversation_history
            
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
                score = chunk.get('score', 0.0)
                
                context_parts.append(
                    f"[Chunk {i+1}] {citation} (relevance: {score:.3f})\n{chunk['text']}"
                )
            
            context = "\n\n".join(context_parts)
            
            # Build conversation history section
            history_section = ""
            conversation_history = state.get('conversation_history', [])
            
            if conversation_history and self.config.get('conversation', 'enable_history', default=True):
                history_section = "\n\n--- CONVERSATION HISTORY ---\n"
                for i, turn in enumerate(conversation_history, 1):
                    history_section += f"\n[Previous Query {i}]: {turn['query']}\n"
                    history_section += f"[Previous Answer {i}]: {turn['answer']}\n"
                history_section += "\n--- END OF HISTORY ---\n"
            
            # Check if this is a retry with feedback
            feedback_section = ""
            if state.get('is_retry') and state.get('judge_feedback'):
                feedback_section = (
                    f"Note: You tried to answer this before, and gave this answer '{state.get('answer', 'N/A')}' "
                    f"but it was not good enough because of {state['judge_feedback']}. "
                    f"Try again and take into consideration this feedback. "
                    f"Do not answer to this feedback, or comment on it. "
                    f"It is only here to make you produce a better answer. Do not reply to it.\n\n"
                )
            
            # Build prompt
            prompt = f"""{feedback_section}You are a code analysis assistant for the httpx library.
Answer the question using ONLY the provided code chunks.

{history_section}

Code Context:
{context}

--- CURRENT USER QUERY ---
Question: {state['query']}

Instructions:
- Answer based ONLY on the code chunks provided above
- Include specific file:line citations in your answer (e.g., httpx/_client.py:45-67)
- Be concise and accurate
- If the context doesn't contain enough information, say so clearly
- DO NOT make up information not present in the chunks
- Reference previous conversation if relevant to the current query

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
            state['error'] = str(e)
        
        return state
    
    def _judge_answer(self, state: RAGState) -> RAGState:
        """Node: Judge answer quality using LLM judge.
        
        Evaluates the answer based on grounding in retrieved chunks.
        Sets judge_score and judge_feedback for retry logic.
        
        Args:
            state: Current RAG state with answer and chunks
            
        Returns:
            Updated state with judge evaluation
        """
        # Skip if error or judge not enabled
        if state.get('error') or not self.judge:
            state['judge_score'] = 5  # Default to pass if judge disabled
            state['judge_feedback'] = None
            return state
        
        try:
            # Evaluate answer
            score, feedback = self.judge.evaluate_answer(
                query=state['query'],
                retrieved_chunks=state['retrieved_chunks'],
                answer=state['answer']
            )
            
            state['judge_score'] = score
            state['judge_feedback'] = feedback
            
        except Exception as e:
            # On error, default to neutral score
            print(f"Judge error: {e}")
            state['judge_score'] = 4
            state['judge_feedback'] = None
        
        return state
    
    def _validate_answer(self, state: RAGState) -> RAGState:
        """Node: Validate answer quality.
        
        Checks:
        - Answer contains citations (if configured)
        - Answer meets minimum length (if configured)
        - Answer is grounded in context (if configured)
        
        Args:
            state: Current RAG state with answer
            
        Returns:
            Updated state with validation results
        """
        if state.get('error'):
            state['validation_passed'] = False
            state['validation_message'] = f"Validation skipped due to error: {state['error']}"
            return state
        
        validation_issues = []
        answer = state['answer']
        
        # Check if validation is enabled
        if not self.config.get('validation', 'require_citations', default=True):
            state['validation_passed'] = True
            state['validation_message'] = "Validation disabled in config"
            return state
        
        # Check 1: Citations present
        if self.config.get('validation', 'require_citations', default=True):
            # Look for file:line patterns
            citation_pattern = r'\w+[/\\][\w/\\._-]+:\d+(?:-\d+)?'
            citations = re.findall(citation_pattern, answer)
            
            if not citations:
                validation_issues.append(
                    "Answer lacks specific file:line citations"
                )
        
        # Check 2: Minimum length
        min_length = self.config.get('validation', 'min_answer_length', default=50)
        if len(answer) < min_length:
            validation_issues.append(
                f"Answer too short ({len(answer)} < {min_length} characters)"
            )
        
        # Check 3: Grounding check (basic)
        if self.config.get('validation', 'check_grounding', default=True):
            # Check if answer contains hedge words when uncertain
            uncertainty_phrases = [
                "I don't have enough information",
                "The provided context doesn't",
                "I cannot find",
                "not enough information"
            ]
            has_hedge = any(phrase.lower() in answer.lower() for phrase in uncertainty_phrases)
            
            # If answer is very short and has no citations, but also no hedge, flag it
            if len(answer) < 100 and not re.search(citation_pattern, answer) and not has_hedge:
                validation_issues.append(
                    "Answer may not be properly grounded (no citations and no uncertainty expressed)"
                )
        
        # Set validation results
        if validation_issues:
            state['validation_passed'] = False
            state['validation_message'] = "Validation issues: " + "; ".join(validation_issues)
        else:
            state['validation_passed'] = True
            state['validation_message'] = "Answer passed all validation checks"
        
        return state
    
    def _should_retry(self, state: RAGState) -> str:
        """Conditional edge function to determine retry logic.
        
        Args:
            state: Current RAG state with judge score
            
        Returns:
            Next node name: "retry" or "finalize"
        """
        # Check if judge is enabled and we should retry
        if not self.judge:
            return "finalize"
        
        score = state.get('judge_score', 5)
        retry_count = state.get('retry_count', 0)
        max_retries = self.config.get('judge', 'max_retries', default=1)
        
        # Retry if score is 1-2 and we haven't exceeded max retries
        if score <= 2 and retry_count < max_retries:
            return "retry"
        else:
            return "finalize"
    
    def _prepare_retry(self, state: RAGState) -> RAGState:
        """Node: Prepare state for retry attempt.
        
        Args:
            state: Current RAG state
            
        Returns:
            Updated state ready for retry
        """
        state['retry_count'] = state.get('retry_count', 0) + 1
        state['is_retry'] = True
        # Keep the feedback and previous answer for context
        return state
    
    def _finalize_answer(self, state: RAGState) -> RAGState:
        """Node: Finalize answer with appropriate messages.
        
        Adds confidence warnings or cannot-help messages based on score.
        
        Args:
            state: Current RAG state
            
        Returns:
            Updated state with finalized answer
        """
        if not self.judge:
            # No judge, use original validation
            return state
        
        score = state.get('judge_score', 5)
        
        # Check if this is a failed retry
        if score <= 2 and state.get('retry_count', 0) >= self.config.get('judge', 'max_retries', default=1):
            # Replace with cannot-help message
            state['answer'] = self.judge.get_cannot_help_message()
        else:
            # Add confidence warning if needed
            confidence_msg = self.judge.get_confidence_message(score)
            if confidence_msg:
                state['answer'] += confidence_msg
        
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
        
        # Add judge and related nodes if enabled
        if self.judge:
            workflow.add_node("judge_answer", self._judge_answer)
            workflow.add_node("prepare_retry", self._prepare_retry)
            workflow.add_node("finalize_answer", self._finalize_answer)
        
        workflow.add_node("validate_answer", self._validate_answer)
        
        # Define edges
        workflow.set_entry_point("embed_query")
        workflow.add_edge("embed_query", "retrieve_chunks")
        workflow.add_edge("retrieve_chunks", "build_context")
        workflow.add_edge("build_context", "generate_answer")
        
        if self.judge:
            # With judge: generate → judge → conditional routing
            workflow.add_edge("generate_answer", "judge_answer")
            workflow.add_conditional_edges(
                "judge_answer",
                self._should_retry,
                {
                    "retry": "prepare_retry",
                    "finalize": "finalize_answer"
                }
            )
            workflow.add_edge("prepare_retry", "build_context")  # Retry loop
            workflow.add_edge("finalize_answer", "validate_answer")
        else:
            # Without judge: generate → validate
            workflow.add_edge("generate_answer", "validate_answer")
        
        workflow.add_edge("validate_answer", END)
        
        return workflow.compile()
    
    def query(self, user_query: str) -> str:
        """Execute the RAG pipeline with conversation history support.
        
        Args:
            user_query: User's question about the codebase
            
        Returns:
            Generated answer with citations
        """
        # Prepare initial state with conversation history
        initial_state: RAGState = {
            "query": user_query,
            "conversation_history": self.conversation_history.copy(),
            "query_embedding": None,
            "retrieved_chunks": [],
            "context": "",
            "answer": "",
            "validation_passed": False,
            "validation_message": "",
            "judge_score": None,
            "judge_feedback": None,
            "retry_count": 0,
            "is_retry": False,
            "error": None
        }
        
        # Run the graph
        final_state = self.graph.invoke(initial_state)
        
        # Update conversation history if answer is valid
        if final_state['validation_passed'] and not final_state.get('error'):
            max_history = self.config.get('conversation', 'max_history_turns', default=5)
            
            # Add to history
            self.conversation_history.append({
                'query': user_query,
                'answer': final_state['answer']
            })
            
            # Keep only last N turns
            if len(self.conversation_history) > max_history:
                self.conversation_history = self.conversation_history[-max_history:]
        
        # Return answer with validation info if it failed
        answer = final_state['answer']
        
        # Note: Judge messages are already added in _finalize_answer node
        # Only add validation message if judge is disabled
        if not self.judge and not final_state['validation_passed']:
            answer += f"\n\n[Validation Note: {final_state['validation_message']}]"
        
        return answer
    
    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history = []
    
    def get_history(self) -> List[ConversationTurn]:
        """Get current conversation history.
        
        Returns:
            List of conversation turns
        """
        return self.conversation_history.copy()
