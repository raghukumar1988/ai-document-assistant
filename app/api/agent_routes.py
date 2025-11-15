from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.agent_simple import get_agent_service  # Changed import
from app.tools import get_tool_names
from app.logger import setup_logger
import json

router = APIRouter(prefix="/api/agent", tags=["agent"])
logger = setup_logger("docuchat.agent_routes")

class ChatMessage(BaseModel):
    """Chat message model"""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")

class AgentRequest(BaseModel):
    """Agent request model"""
    query: str = Field(..., description="User query", min_length=1)
    chat_history: Optional[List[ChatMessage]] = Field(
        default=None,
        description="Optional chat history for context"
    )

class ToolUsage(BaseModel):
    """Tool usage information"""
    tool: str
    tool_input: Any
    observation: str

class AgentResponse(BaseModel):
    """Agent response model"""
    output: str = Field(..., description="Agent's final answer")
    tool_usage: List[Dict[str, Any]] = Field(..., description="Tools used by agent")
    success: bool = Field(..., description="Whether execution succeeded")
    request_id: str = Field(..., description="Request ID")

@router.get("/tools")
async def list_tools(request: Request):
    """
    List all available tools the agent can use
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info("Listing available agent tools", extra={"request_id": request_id})
    
    try:
        tool_names = get_tool_names()
        
        return {
            "tools": tool_names,
            "total_tools": len(tool_names),
            "descriptions": {
                "Calculator": "Perform mathematical calculations",
                "WebSearch": "Search the internet for current information",
                "DocumentSearch": "Search through uploaded documents",
                "ListDocuments": "List all processed documents"
            },
            "request_id": request_id
        }
    except Exception as e:
        logger.error(f"Failed to list tools: {str(e)}", extra={"request_id": request_id})
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/run", response_model=AgentResponse)
async def run_agent(request: Request, agent_request: AgentRequest):
    """
    Run agent with tools to answer queries
    
    The agent can:
    - Perform calculations
    - Search the web
    - Search documents
    - Combine multiple tools
    
    Examples:
    - "What is 25 * 47 + 100?"
    - "Search the web for recent AI news"
    - "What documents do I have and what are they about?"
    - "Calculate the square root of 144 and search for its significance"
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        "Agent request received",
        extra={
            "request_id": request_id,
            "query": agent_request.query[:100]
        }
    )
    
    try:
        # Get agent service
        agent_service = get_agent_service()
        
        # Convert chat history
        chat_history = None
        if agent_request.chat_history:
            chat_history = [
                {"role": msg.role, "content": msg.content}
                for msg in agent_request.chat_history
            ]
        
        # Run agent
        result = await agent_service.run_agent(
            query=agent_request.query,
            chat_history=chat_history,
            request_id=request_id
        )
        
        if not result["success"]:
            logger.error(
                f"Agent execution failed",
                extra={"request_id": request_id, "error": result.get("error")}
            )
        
        return AgentResponse(
            output=result["output"],
            tool_usage=result["tool_usage"],
            success=result["success"],
            request_id=request_id
        )
        
    except Exception as e:
        logger.error(
            f"Agent request failed: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stream")
async def run_agent_stream(request: Request, agent_request: AgentRequest):
    """
    Run agent with streaming output
    
    Shows tool usage and reasoning in real-time:
    - tool_start: When agent decides to use a tool
    - tool_end: When tool completes
    - message: Final answer chunks
    - done: Completion
    
    Example: "Calculate 15% tip on $47.50 and search for tipping etiquette"
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        "Streaming agent request received",
        extra={
            "request_id": request_id,
            "query": agent_request.query[:100]
        }
    )
    
    async def event_generator():
        try:
            # Send start event
            yield {
                "event": "start",
                "data": json.dumps({
                    "request_id": request_id,
                    "status": "Agent thinking..."
                })
            }
            
            # Get agent service
            agent_service = get_agent_service()
            
            # Convert chat history
            chat_history = None
            if agent_request.chat_history:
                chat_history = [
                    {"role": msg.role, "content": msg.content}
                    for msg in agent_request.chat_history
                ]
            
            # Stream agent execution
            tools_used = []
            full_response = ""
            
            async for event in agent_service.run_agent_stream(
                query=agent_request.query,
                chat_history=chat_history,
                request_id=request_id
            ):
                event_type = event["type"]
                event_data = event["data"]
                
                if event_type == "tool_start":
                    tools_used.append(event_data["tool"])
                    yield {
                        "event": "tool_start",
                        "data": json.dumps(event_data)
                    }
                
                elif event_type == "tool_end":
                    yield {
                        "event": "tool_end",
                        "data": json.dumps(event_data)
                    }
                
                elif event_type == "message":
                    chunk = event_data["chunk"]
                    full_response += chunk
                    yield {
                        "event": "message",
                        "data": json.dumps({
                            "chunk": chunk,
                            "full_text": full_response
                        })
                    }
                
                elif event_type == "done":
                    yield {
                        "event": "done",
                        "data": json.dumps({
                            "request_id": request_id,
                            "status": "completed",
                            "tools_used": tools_used,
                            "full_response": full_response
                        })
                    }
                
                elif event_type == "error":
                    yield {
                        "event": "error",
                        "data": json.dumps(event_data)
                    }
            
        except Exception as e:
            logger.error(
                f"Streaming agent failed: {str(e)}",
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
    
    return EventSourceResponse(event_generator())

@router.post("/test")
async def test_tools(request: Request):
    """
    Test that all agent tools are working
    
    Runs a simple test with each tool
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info("Testing agent tools", extra={"request_id": request_id})
    
    test_results = {}
    
    try:
        agent_service = get_agent_service()
        
        # Test calculator
        try:
            calc_result = await agent_service.run_agent(
                query="What is 2 + 2?",
                request_id=request_id
            )
            test_results["calculator"] = {
                "status": "success" if calc_result["success"] else "failed",
                "output": calc_result["output"][:200]
            }
        except Exception as e:
            test_results["calculator"] = {"status": "error", "error": str(e)}
        
        # Test web search
        try:
            search_result = await agent_service.run_agent(
                query="What is the current date?",
                request_id=request_id
            )
            test_results["web_search"] = {
                "status": "success" if search_result["success"] else "failed",
                "output": search_result["output"][:200]
            }
        except Exception as e:
            test_results["web_search"] = {"status": "error", "error": str(e)}
        
        # Test document list
        try:
            doc_result = await agent_service.run_agent(
                query="What documents do I have?",
                request_id=request_id
            )
            test_results["document_list"] = {
                "status": "success" if doc_result["success"] else "failed",
                "output": doc_result["output"][:200]
            }
        except Exception as e:
            test_results["document_list"] = {"status": "error", "error": str(e)}
        
        return {
            "test_results": test_results,
            "overall_status": "all tools tested",
            "request_id": request_id
        }
        
    except Exception as e:
        logger.error(
            f"Tool testing failed: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))