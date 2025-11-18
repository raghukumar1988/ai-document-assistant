from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from app.llm import get_llm_service
from app.logger import setup_logger
import json
import asyncio

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
            "chat_message": chat_request.message[:100],  # Log first 100 chars
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
    Stream AI responses in real-time using Server-Sent Events (SSE)
    
    - **message**: Your question or message
    - **chat_history**: Optional previous conversation for context
    - **system_prompt**: Optional custom system prompt
    
    Returns a stream of Server-Sent Events with chunks as they arrive
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        "Streaming chat request received",
        extra={
            "request_id": request_id,
            "chat_message": chat_request.message[:100],
        }
    )
    
    async def event_generator():
        try:
            # Send start event
            yield {
                "event": "start",
                "data": json.dumps({
                    "request_id": request_id,
                    "status": "generating"
                })
            }
            
            # Get LLM service
            llm_service = get_llm_service()
            
            # Convert chat history
            chat_history = None
            if chat_request.chat_history:
                chat_history = [
                    {"role": msg.role, "content": msg.content}
                    for msg in chat_request.chat_history
                ]
            
            # Stream response chunks
            full_response = ""
            async for chunk in llm_service.chat_stream(
                message=chat_request.message,
                chat_history=chat_history,
                system_prompt=chat_request.system_prompt,
                request_id=request_id
            ):
                full_response += chunk
                yield {
                    "event": "message",
                    "data": json.dumps({
                        "chunk": chunk,
                        "full_text": full_response
                    })
                }
            
            # Send completion event
            yield {
                "event": "done",
                "data": json.dumps({
                    "request_id": request_id,
                    "status": "completed",
                    "full_response": full_response
                })
            }
            
            logger.info(
                "Streaming completed successfully",
                extra={
                    "request_id": request_id,
                    "response_length": len(full_response)
                }
            )
            
        except Exception as e:
            logger.error(
                f"Streaming error: {str(e)}",
                extra={"request_id": request_id},
                exc_info=True
            )
            yield {
                "event": "error",
                "data": json.dumps({
                    "error": str(e),
                    "request_id": request_id
                })
            }
    
    return EventSourceResponse(event_generator(), media_type="text/event-stream")