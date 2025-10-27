"""LLM client wrapper for Google Gemini."""
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from tenacity import retry, stop_after_attempt, wait_exponential
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class LLMService:
    """Service for interacting with Google Gemini LLM."""
    
    def __init__(self):
        """Initialize the LLM service."""
        self.llm = ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.google_api_key,
            temperature=settings.llm_temperature,
            max_output_tokens=settings.llm_max_tokens,
            convert_system_message_to_human=True,  # Gemini doesn't support system messages
        )
        logger.info(
            "LLM service initialized",
            model=settings.llm_model,
            temperature=settings.llm_temperature
        )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        stream: bool = False
    ) -> str:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            stream: Whether to stream the response
            
        Returns:
            Generated text response
        """
        try:
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))
            
            if stream:
                # For streaming, we'll return an async generator
                response = await self.llm.astream(messages)
                return response
            else:
                response = await self.llm.ainvoke(messages)
                logger.debug("Generated LLM response", prompt_length=len(prompt))
                return response.content
        except Exception as e:
            logger.error("Failed to generate LLM response", error=str(e))
            raise
    
    def generate_sync(
        self,
        prompt: str,
        system_prompt: str | None = None
    ) -> str:
        """
        Generate a response from the LLM (synchronous).
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            
        Returns:
            Generated text response
        """
        try:
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))
            
            response = self.llm.invoke(messages)
            logger.debug("Generated LLM response (sync)", prompt_length=len(prompt))
            return response.content
        except Exception as e:
            logger.error("Failed to generate LLM response (sync)", error=str(e))
            raise


# Global LLM service instance
llm_service = LLMService()
