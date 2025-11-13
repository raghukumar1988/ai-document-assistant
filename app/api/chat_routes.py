from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from app.llm import get_llm_service
from app.logger import setup_logger
import json

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = setup_logger("docuchat.chat_routes")

class ChatMessage(BaseModel):
    """Chat message model"""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")

class ChatRequest(BaseModel):
    """Chat request model"""
    message: str = Field(..., description="User message", min_length=1)
    chat_history: Optional[List[ChatMessage]] = Field(
        default=None,
        description="Optional chat history for context"
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description="Optional system prompt override"
    )

class ChatResponse(BaseModel):
    """Chat response model"""
    response: str = Field(..., description="AI response")
    request_id: str = Field(..., description="Request ID for tracking")

@router.post("/", response_model=ChatResponse)
async def chat(request: Request, chat_request: ChatRequest):
    """
    Send a message to the AI and get a response
    
    - **message**: Your question or message
    - **chat_history**: Optional previous conversation for context
    - **system_prompt**: Optional custom system prompt
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        f"Chat request received",
        extra={
            "request_id": request_id,
            "user_message": chat_request.message[:100],  # Log first 100 chars
            "has_history": bool(chat_request.chat_history),
        }
    )
    
    try:
        # Get LLM service
        llm_service = get_llm_service()
        
        # Convert chat history to dict format
        chat_history = None
        if chat_request.chat_history:
            chat_history = [
                {"role": msg.role, "content": msg.content}
                for msg in chat_request.chat_history
            ]
        
        # Get response
        response = await llm_service.chat(
            message=chat_request.message,
            chat_history=chat_history,
            system_prompt=chat_request.system_prompt,
            request_id=request_id
        )
        
        logger.info(
            f"Chat response generated successfully",
            extra={
                "request_id": request_id,
                "response_length": len(response),
            }
        )
        
        return ChatResponse(
            response=response,
            request_id=request_id
        )
        
    except ValueError as e:
        logger.error(
            f"Configuration error: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Azure OpenAI configuration error: {str(e)}"
        )
    
    except Exception as e:
        logger.error(
            f"Chat request failed: {str(e)}",
            extra={"request_id": request_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat request: {str(e)}"
        )

@router.post("/stream")
async def chat_stream(request: Request, chat_request: ChatRequest):
    """
    Stream AI responses in real-time (for Phase 6)
    
    - **message**: Your question or message
    - **chat_history**: Optional previous conversation for context
    - **system_prompt**: Optional custom system prompt
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        f"Streaming chat request received",
        extra={
            "request_id": request_id,
            "user_message": chat_request.message[:100],
        }
    )
    
    try:
        # Get LLM service
        llm_service = get_llm_service()
        
        # Convert chat history
        chat_history = None
        if chat_request.chat_history:
            chat_history = [
                {"role": msg.role, "content": msg.content}
                for msg in chat_request.chat_history
            ]
        
        # Stream response
        async def generate():
            try:
                async for chunk in llm_service.chat_stream(
                    message=chat_request.message,
                    chat_history=chat_history,
                    system_prompt=chat_request.system_prompt,
                    request_id=request_id
                ):
                    # Send chunk as SSE (Server-Sent Events)
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                
                # Send done signal
                yield f"data: {json.dumps({'done': True})}\n\n"
                
            except Exception as e:
                logger.error(
                    f"Streaming error: {str(e)}",
                    extra={"request_id": request_id},
                    exc_info=True
                )
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-ID": request_id,
            }
        )
        
    except Exception as e:
        logger.error(
            f"Stream setup failed: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to setup streaming: {str(e)}"
        )

@router.get("/test")
async def test_connection(request: Request):
    """
    Test Azure OpenAI connection
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info("Testing Azure OpenAI connection", extra={"request_id": request_id})
    
    try:
        llm_service = get_llm_service()
        
        # Simple test message
        response = await llm_service.chat(
            message="Say 'Hello! Azure OpenAI is working!' if you can read this.",
            request_id=request_id
        )
        
        return {
            "status": "success",
            "message": "Azure OpenAI connection is working",
            "test_response": response,
            "request_id": request_id
        }
        
    except Exception as e:
        logger.error(
            f"Connection test failed: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Azure OpenAI connection failed: {str(e)}"
        )