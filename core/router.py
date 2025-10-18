"""Query Router for relevance classification and query refinement.

This module implements a query router that uses an LLM to:
1. Classify if a query is relevant to the httpx library
2. Generate contextual rejection messages for irrelevant queries
3. Fine-tune relevant queries for better embedding quality
"""

import os
import json
import logging
from typing import Dict, Tuple, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from .config import Config

logger = logging.getLogger(__name__)


class QueryRouter:
    """Router for query relevance classification and refinement.
    
    Uses an LLM to classify queries as relevant/irrelevant to httpx
    and refine relevant queries for better embedding performance.
    """
    
    def __init__(self, config: Config):
        """Initialize the query router.
        
        Args:
            config: Config object with router settings
            
        Raises:
            EnvironmentError: If API key is not set
        """
        self.config = config
        
        # Load environment variables
        load_dotenv()
        
        # Initialize LLM for routing
        api_key_env = config.get('llm', 'api_key_env')
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise EnvironmentError(
                f"Missing environment variable: {api_key_env}. "
                f"Please set it in your .env file."
            )
        
        # Use router-specific config if available, otherwise use main LLM config
        router_model = config.get('router', 'model', default=config.get('llm', 'model'))
        router_temp = config.get('router', 'temperature', default=0.0)
        
        self.llm = ChatOpenAI(
            model=router_model,
            temperature=router_temp,
            max_tokens=500,
            api_key=api_key
        )
        
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for query classification and refinement.
        
        Returns:
            System prompt string with few-shot examples
        """
        return """You are a query classifier and refiner for an httpx library documentation assistant.

Your task is to:
1. Determine if a user's query is RELEVANT to the httpx Python library
2. Generate a contextual rejection message if irrelevant
3. Refine relevant queries for better semantic search

## RELEVANT TOPICS (httpx library)
- HTTP requests (GET, POST, PUT, DELETE, etc.)
- SSL/TLS certificate validation and configuration
- Authentication methods (Basic, Digest, Bearer tokens, OAuth)
- Proxy configuration and usage
- Request/response timeouts
- Async/await patterns and async clients
- HTTP/2 support
- Request/response models and headers
- Cookies and session management
- Event hooks and middleware
- Transport layers (ASGI, WSGI)
- Error handling and exceptions
- Connection pooling
- Streaming responses
- Multipart file uploads

## IRRELEVANT TOPICS
- General Python programming unrelated to httpx
- Other HTTP libraries (requests, aiohttp, urllib3, etc.)
- Questions about specific websites or APIs (not httpx itself)
- Personal questions or general knowledge
- Toxic, harmful, or inappropriate content
- Questions about people, places, or events
- Math, science, or other non-programming topics

## OUTPUT FORMAT
Respond ONLY with a valid JSON object (no markdown, no extra text):
{
  "is_relevant": true/false,
  "reason": "brief explanation of classification",
  "refined_query": "cleaned query optimized for embedding (only if relevant, else null)",
  "rejection_message": "helpful message to user (only if irrelevant, else null)"
}

## REFINEMENT STRATEGY (for relevant queries)
- Remove slang, informal language, and filler words
- Expand abbreviations and clarify technical terms
- Make the query more specific and technical
- Maintain the core semantic intent
- Optimize for vector similarity search

## REJECTION MESSAGES (for irrelevant queries)
- Be polite and helpful
- Explain why the query is out of scope
- Guide user back to httpx-related topics
- For toxic content: firmly decline without engaging

## FEW-SHOT EXAMPLES

Example 1 (Relevant - informal):
User: "yo bro, what is ssl in httpx?"
Output: {
  "is_relevant": true,
  "reason": "Query about SSL/TLS in httpx (valid topic)",
  "refined_query": "What role does SSL/TLS certificate validation play in httpx?",
  "rejection_message": null
}

Example 2 (Relevant - formal):
User: "How does httpx handle request timeouts?"
Output: {
  "is_relevant": true,
  "reason": "Query about timeout handling in httpx (valid topic)",
  "refined_query": "How does httpx handle request timeouts and timeout configuration?",
  "rejection_message": null
}

Example 3 (Irrelevant - off-topic):
User: "Who is LeBron James?"
Output: {
  "is_relevant": false,
  "reason": "Query about a person, not related to httpx library",
  "refined_query": null,
  "rejection_message": "I'm sorry, but I'm specifically designed to help with questions about the httpx Python library. Questions about people, sports, or general knowledge are outside my scope. Please ask me about httpx features like SSL validation, authentication, timeouts, proxies, or async requests."
}

Example 4 (Irrelevant - wrong library):
User: "How do I use requests library to make POST requests?"
Output: {
  "is_relevant": false,
  "reason": "Query about 'requests' library, not httpx",
  "refined_query": null,
  "rejection_message": "I specialize in the httpx library, not the requests library. While they're similar, I can only help with httpx-specific questions. If you'd like to know how httpx handles POST requests, I'd be happy to help with that!"
}

Example 5 (Irrelevant - toxic):
User: "How do I hack someone's password?"
Output: {
  "is_relevant": false,
  "reason": "Inappropriate request for harmful activity",
  "refined_query": null,
  "rejection_message": "I cannot help with requests related to hacking, unauthorized access, or any potentially harmful activities. I'm here to help you understand and use the httpx library for legitimate HTTP client functionality. Please ask about proper authentication methods or security features in httpx if that's your interest."
}

Example 6 (Relevant - needs refinement):
User: "does httpx support http2 stuff?"
Output: {
  "is_relevant": true,
  "reason": "Query about HTTP/2 support in httpx (valid topic)",
  "refined_query": "Does httpx support HTTP/2 protocol?",
  "rejection_message": null
}

Example 7 (Irrelevant - general programming):
User: "What's the difference between a list and a tuple in Python?"
Output: {
  "is_relevant": false,
  "reason": "General Python question, not specific to httpx",
  "refined_query": null,
  "rejection_message": "I'm specialized in answering questions about the httpx library specifically. For general Python programming questions, you might want to consult Python documentation or general programming resources. If you have questions about how httpx uses Python features or httpx-specific functionality, I'm here to help!"
}

Now classify and refine the following query:"""
    
    def classify_and_refine(self, query: str) -> Dict[str, any]:
        """Classify query relevance and refine if relevant.
        
        Args:
            query: User's query string
            
        Returns:
            Dictionary with keys:
                - is_relevant: bool
                - reason: str
                - refined_query: Optional[str]
                - rejection_message: Optional[str]
        """
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": query}
            ]
            
            response = self.llm.invoke(messages)
            result_text = response.content.strip()
            
            # Parse JSON response
            # Remove markdown code blocks if present
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
                result_text = result_text.strip()
            
            result = json.loads(result_text)
            
            # Validate required fields
            required_fields = ['is_relevant', 'reason']
            if not all(field in result for field in required_fields):
                raise ValueError(f"Missing required fields in router response: {result}")
            
            logger.info(f"Query classified as {'relevant' if result['is_relevant'] else 'irrelevant'}: {result['reason']}")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse router response as JSON: {e}")
            logger.error(f"Response was: {result_text}")
            # Default to relevant to avoid blocking valid queries
            return {
                'is_relevant': True,
                'reason': 'Router parsing failed, defaulting to relevant',
                'refined_query': query,
                'rejection_message': None
            }
        except Exception as e:
            logger.error(f"Router error: {e}")
            # Default to relevant to avoid blocking valid queries
            return {
                'is_relevant': True,
                'reason': f'Router error: {e}, defaulting to relevant',
                'refined_query': query,
                'rejection_message': None
            }

