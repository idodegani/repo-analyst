"""Answer Judge for RAG Pipeline.

This module implements an LLM-based judge that evaluates answer quality
based on grounding in retrieved chunks. Scores answers from 1-6 and
provides feedback for improvement.
"""

import os
import json
from typing import Dict, List, Optional, Tuple
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

from .config import Config


class AnswerJudge:
    """LLM Judge for evaluating answer grounding quality.
    
    Scores answers from 1-6 based on how well they are grounded in
    the retrieved context. Provides feedback for low scores to enable
    retry with improvements.
    
    Score Interpretations:
        6: Perfect grounding with clear citations
        5: Well-grounded with minor issues
        4: Mostly grounded but some concerns
        3: Partially grounded, needs caution
        2: Poorly grounded, significant issues
        1: Not grounded, speculation or off-topic
    """
    
    def __init__(self, config: Config):
        """Initialize the Answer Judge.
        
        Args:
            config: Configuration object with judge settings
            
        Raises:
            EnvironmentError: If API key is not set
        """
        self.config = config
        
        # Load environment variables
        load_dotenv()
        
        # Initialize judge LLM (can be different from main LLM for independence)
        api_key_env = config.get('llm', 'api_key_env')
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise EnvironmentError(
                f"Missing environment variable: {api_key_env}. "
                f"Please set it in your .env file."
            )
        
        # Use judge-specific config if available, otherwise use main LLM config
        judge_model = config.get('judge', 'model', default=config.get('llm', 'model'))
        judge_temperature = config.get('judge', 'temperature', default=0.0)
        
        self.llm = ChatOpenAI(
            model=judge_model,
            temperature=judge_temperature,
            max_tokens=500,
            api_key=api_key
        )
        
        # Load thresholds
        self.high_threshold = config.get('judge', 'confidence_thresholds', 'high', default=5)
        self.medium_threshold = config.get('judge', 'confidence_thresholds', 'medium', default=3)
    
    def evaluate_answer(
        self, 
        query: str, 
        retrieved_chunks: List[Dict], 
        answer: str
    ) -> Tuple[int, Optional[str]]:
        """Evaluate an answer's grounding quality.
        
        Args:
            query: The user's original question
            retrieved_chunks: List of retrieved context chunks
            answer: The generated answer to evaluate
            
        Returns:
            Tuple of (score, feedback) where:
                - score: Integer from 1-6
                - feedback: Optional feedback string (only for scores 1-2)
        """
        # Format chunks for judge
        context_summary = self._format_chunks_for_judge(retrieved_chunks)
        
        # Build judge prompt
        judge_prompt = self._build_judge_prompt(query, context_summary, answer)
        
        try:
            # Get judge evaluation
            messages = [
                {"role": "system", "content": "You are an expert judge evaluating answer quality based on evidence grounding."},
                {"role": "user", "content": judge_prompt}
            ]
            
            response = self.llm.invoke(messages)
            
            # Parse judge response
            score, feedback = self._parse_judge_response(response.content)
            
            return score, feedback
            
        except Exception as e:
            # On error, return neutral score to avoid blocking
            print(f"Judge evaluation error: {e}")
            return 4, None
    
    def _format_chunks_for_judge(self, chunks: List[Dict]) -> str:
        """Format retrieved chunks for judge evaluation.
        
        Args:
            chunks: List of retrieved chunks with metadata
            
        Returns:
            Formatted string summarizing the evidence
        """
        if not chunks:
            return "No context chunks were retrieved."
        
        evidence_parts = []
        for i, chunk in enumerate(chunks, 1):
            file_path = chunk.get('file_path', 'unknown')
            start_line = chunk.get('start_line', '?')
            end_line = chunk.get('end_line', '?')
            score = chunk.get('score', 0.0)
            text = chunk.get('text', '')
            
            # Truncate very long chunks for judge
            if len(text) > 500:
                text = text[:500] + "..."
            
            evidence_parts.append(
                f"Evidence {i} [{file_path}:{start_line}-{end_line}] (relevance: {score:.3f}):\n{text}"
            )
        
        return "\n\n".join(evidence_parts)
    
    def _build_judge_prompt(self, query: str, context: str, answer: str) -> str:
        """Build the prompt for the judge LLM.
        
        Args:
            query: Original user query
            context: Formatted evidence chunks
            answer: Generated answer to evaluate
            
        Returns:
            Complete prompt for judge evaluation
        """
        return f"""Evaluate the quality of this answer based on how well it is grounded in the provided evidence.

USER QUERY:
{query}

AVAILABLE EVIDENCE:
{context}

GENERATED ANSWER:
{answer}

SCORING CRITERIA:
- Score 6: Perfect grounding - all claims directly supported by evidence with proper citations
- Score 5: Well-grounded - minor citation issues but claims match evidence
- Score 4: Mostly grounded - main points supported but some minor unsupported details
- Score 3: Partially grounded - mix of supported and unsupported claims
- Score 2: Poorly grounded - mostly speculation or misinterpretation of evidence
- Score 1: Not grounded - completely off-topic or pure speculation

EVALUATION INSTRUCTIONS:
1. Check if the answer includes file:line citations
2. Verify each claim in the answer against the available evidence
3. Look for any speculation or claims beyond the evidence
4. Assess if the answer fully addresses the query based on available evidence
5. Check for misinterpretation or misrepresentation of the evidence

RESPONSE FORMAT:
Provide your response in this exact JSON format:
{{
    "score": <integer from 1-6>,
    "reasoning": "<brief explanation of score>",
    "feedback": "<30-40 word feedback ONLY if score is 1-2, otherwise null>"
}}

The feedback should be constructive and specific, explaining what needs improvement.
Focus on grounding issues, missing citations, or speculation beyond evidence."""
    
    def _parse_judge_response(self, response: str) -> Tuple[int, Optional[str]]:
        """Parse the judge's response to extract score and feedback.
        
        Args:
            response: Raw response from judge LLM
            
        Returns:
            Tuple of (score, feedback)
        """
        try:
            # Try to parse as JSON
            result = json.loads(response)
            score = int(result.get('score', 4))
            
            # Ensure score is in valid range
            score = max(1, min(6, score))
            
            # Get feedback only for low scores
            feedback = None
            if score <= 2:
                feedback = result.get('feedback')
                if feedback and len(feedback) > 150:
                    # Truncate overly long feedback
                    feedback = feedback[:147] + "..."
            
            return score, feedback
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract score from text
            import re
            
            # Look for score patterns
            score_match = re.search(r'score[:\s]+(\d)', response, re.IGNORECASE)
            if score_match:
                score = int(score_match.group(1))
                score = max(1, min(6, score))
            else:
                # Default to neutral score
                score = 4
            
            # Try to extract feedback for low scores
            feedback = None
            if score <= 2:
                feedback_match = re.search(r'feedback[:\s]+(.+?)(?:\n|$)', response, re.IGNORECASE)
                if feedback_match:
                    feedback = feedback_match.group(1).strip()[:150]
            
            return score, feedback
    
    def get_confidence_message(self, score: int) -> Optional[str]:
        """Get appropriate confidence message based on score.
        
        Args:
            score: Judge score from 1-6
            
        Returns:
            Optional warning message for medium confidence scores
        """
        if score >= self.high_threshold:
            # High confidence - no message needed
            return None
        elif score >= self.medium_threshold:
            # Medium confidence - add warning
            return (
                "\n\n[Note: Low confidence in this answer. "
                "The information provided may be incomplete or partially speculative. "
                "Please verify important details.]"
            )
        else:
            # Low confidence - should have triggered retry
            # This is a fallback if retry also failed
            return (
                "\n\n[Warning: Very low confidence in this answer. "
                "The response may not be well-grounded in the available evidence.]"
            )
    
    def get_cannot_help_message(self) -> str:
        """Get standard message when unable to provide grounded answer.
        
        Returns:
            Standardized message for unanswerable queries
        """
        return (
            "I cannot provide a reliable answer to this query based on the available "
            "information in the repository. The evidence found does not sufficiently "
            "support a well-grounded response. Please try rephrasing your question "
            "or asking about a different aspect of the codebase."
        )
