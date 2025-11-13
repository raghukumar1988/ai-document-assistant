from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from app.config import settings, validate_azure_config
from app.logger import setup_logger
from typing import List, Dict

logger = setup_logger("docuchat.llm")

class LLMService:
    """Service for interacting with Azure OpenAI via LangChain"""
    
    def __init__(self):
        """Initialize Azure OpenAI client"""
        try:
            # Validate configuration
            validate_azure_config()
            
            # Initialize Azure ChatOpenAI
            self.llm = AzureChatOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                azure_deployment=settings.azure_openai_deployment_name,
                api_version=settings.azure_openai_api_version,
                api_key=settings.azure_openai_api_key,
                temperature=settings.temperature,
                max_tokens=settings.max_tokens,
            )
            
            logger.info(
                "Azure OpenAI client initialized successfully",
                extra={
                    "deployment": settings.azure_openai_deployment_name,
                    "api_version": settings.azure_openai_api_version,
                    "model": settings.azure_openai_model_name,
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize Azure OpenAI client: {str(e)}", exc_info=True)
            raise
    
    def create_chat_chain(self, system_prompt: str = None):
        """
        Create a chat chain with optional system prompt
        
        Args:
            system_prompt: System prompt to set context
            
        Returns:
            LangChain runnable chain
        """
        if system_prompt is None:
            system_prompt = (
                "You are a helpful AI assistant for DocuChat, an intelligent document assistant. "
                "You help users understand and analyze their documents. "
                "Provide clear, concise, and accurate responses."
            )
        
        # Create prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
        ])
        
        # Create chain: prompt -> llm -> output parser
        chain = prompt | self.llm | StrOutputParser()
        
        return chain
    
    async def chat(
        self,
        message: str,
        chat_history: List[Dict[str, str]] = None,
        system_prompt: str = None,
        request_id: str = None
    ) -> str:
        """
        Send a chat message and get response
        
        Args:
            message: User message
            chat_history: Optional chat history
            system_prompt: Optional system prompt override
            request_id: Request ID for logging
            
        Returns:
            AI response as string
        """
        try:
            logger.info(
                f"Processing chat request",
                extra={
                    "request_id": request_id,
                    "message_length": len(message),
                    "has_history": bool(chat_history),
                }
            )
            
            # Create chain
            chain = self.create_chat_chain(system_prompt)
            
            # Prepare input
            chain_input = {
                "input": message,
                "chat_history": chat_history or []
            }
            
            # Invoke chain
            response = await chain.ainvoke(chain_input)
            
            logger.info(
                f"Chat response generated",
                extra={
                    "request_id": request_id,
                    "response_length": len(response),
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(
                f"Chat request failed: {str(e)}",
                extra={"request_id": request_id, "error": str(e)},
                exc_info=True
            )
            raise
    
    async def chat_stream(
        self,
        message: str,
        chat_history: List[Dict[str, str]] = None,
        system_prompt: str = None,
        request_id: str = None
    ):
        """
        Stream chat response (for future use)
        
        Args:
            message: User message
            chat_history: Optional chat history
            system_prompt: Optional system prompt override
            request_id: Request ID for logging
            
        Yields:
            Response chunks as they arrive
        """
        try:
            logger.info(
                f"Processing streaming chat request",
                extra={
                    "request_id": request_id,
                    "message_length": len(message),
                }
            )
            
            # Create chain
            chain = self.create_chat_chain(system_prompt)
            
            # Prepare input
            chain_input = {
                "input": message,
                "chat_history": chat_history or []
            }
            
            # Stream response
            async for chunk in chain.astream(chain_input):
                yield chunk
            
            logger.info(
                f"Streaming chat completed",
                extra={"request_id": request_id}
            )
            
        except Exception as e:
            logger.error(
                f"Streaming chat failed: {str(e)}",
                extra={"request_id": request_id, "error": str(e)},
                exc_info=True
            )
            raise

# Global LLM service instance
llm_service = None

def get_llm_service() -> LLMService:
    """Get or create global LLM service instance"""
    global llm_service
    if llm_service is None:
        llm_service = LLMService()
    return llm_service