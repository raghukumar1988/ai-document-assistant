from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from app.graph_workflows import get_research_workflow, get_chat_workflow
from app.graph_state import ResearchState, ChatState
from app.logger import setup_logger
from langchain_core.messages import HumanMessage
import json

router = APIRouter(prefix="/api/graph", tags=["langgraph"])
logger = setup_logger("docuchat.graph_routes")

class ResearchRequest(BaseModel):
    """Research workflow request"""
    query: str = Field(..., description="Research query", min_length=1)

class ChatRequest(BaseModel):
    """Chat workflow request"""
    query: str = Field(..., description="Chat message", min_length=1)
    chat_history: Optional[List[dict]] = Field(default=None, description="Previous messages")

class WorkflowResponse(BaseModel):
    """Workflow execution response"""
    result: dict
    steps_executed: List[str]
    request_id: str

@router.post("/research", response_model=WorkflowResponse)
async def run_research_workflow(request: Request, research_request: ResearchRequest):
    """
    Run multi-step research workflow
    
    This workflow:
    1. Creates a research plan
    2. Searches documents if relevant
    3. Searches web if needed
    4. Performs calculations if needed
    5. Synthesizes a comprehensive answer
    
    Example queries:
    - "Research AI developments and calculate market growth"
    - "What do my documents say about Python and how old is the language?"
    - "Calculate 15% of 500 and search for investment tips"
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        "Research workflow started",
        extra={"request_id": request_id, "query": research_request.query[:100]}
    )
    
    try:
        workflow = get_research_workflow()
        
        # Initialize state
        initial_state: ResearchState = {
            "query": research_request.query,
            "messages": [HumanMessage(content=research_request.query)],
            "documents_found": [],
            "web_results": None,
            "calculations": None,
            "research_plan": None,
            "final_answer": None,
            "iterations": 0,
            "needs_approval": False,
            "approved": None,
            "error": None
        }
        
        # Run workflow
        result = await workflow.ainvoke(initial_state)
        
        # Extract steps executed
        steps = []
        if result.get("research_plan"):
            steps.append("plan")
        if result.get("documents_found"):
            steps.append("search_documents")
        if result.get("web_results"):
            steps.append("search_web")
        if result.get("calculations"):
            steps.append("calculate")
        if result.get("final_answer"):
            steps.append("synthesize")
        
        logger.info(
            "Research workflow completed",
            extra={
                "request_id": request_id,
                "steps": len(steps),
                "has_answer": bool(result.get("final_answer"))
            }
        )
        
        return WorkflowResponse(
            result={
                "query": result["query"],
                "research_plan": result.get("research_plan"),
                "documents_found": result.get("documents_found", []),
                "web_results": result.get("web_results"),
                "calculations": result.get("calculations"),
                "final_answer": result.get("final_answer"),
                "iterations": result.get("iterations", 0),
                "error": result.get("error")
            },
            steps_executed=steps,
            request_id=request_id
        )
        
    except Exception as e:
        logger.error(
            f"Research workflow failed: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat", response_model=WorkflowResponse)
async def run_chat_workflow(request: Request, chat_request: ChatRequest):
    """
    Run intelligent chat workflow
    
    This workflow:
    1. Analyzes the query
    2. Decides if document search is needed
    3. Fetches relevant context if needed
    4. Generates contextual response
    
    Example queries:
    - "What's in my documents?"
    - "Tell me about artificial intelligence"
    - "Summarize the uploaded files"
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        "Chat workflow started",
        extra={"request_id": request_id, "query": chat_request.query[:100]}
    )
    
    try:
        workflow = get_chat_workflow()
        
        # Convert chat history
        messages = []
        if chat_request.chat_history:
            from langchain_core.messages import HumanMessage, AIMessage
            for msg in chat_request.chat_history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))
        
        # Initialize state
        initial_state: ChatState = {
            "messages": messages,
            "current_query": chat_request.query,
            "context": None,
            "response": None,
            "should_search_docs": False,
            "should_search_web": False
        }
        
        # Run workflow
        result = await workflow.ainvoke(initial_state)
        
        # Extract steps
        steps = ["analyze"]
        if result.get("context"):
            steps.append("fetch_context")
        if result.get("response"):
            steps.append("generate")
        
        logger.info(
            "Chat workflow completed",
            extra={
                "request_id": request_id,
                "steps": len(steps),
                "used_context": bool(result.get("context"))
            }
        )
        
        return WorkflowResponse(
            result={
                "query": result["current_query"],
                "response": result.get("response"),
                "used_documents": result.get("should_search_docs", False),
                "context_provided": bool(result.get("context"))
            },
            steps_executed=steps,
            request_id=request_id
        )
        
    except Exception as e:
        logger.error(
            f"Chat workflow failed: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/research/stream")
async def stream_research_workflow(request: Request, research_request: ResearchRequest):
    """
    Stream research workflow execution
    
    Shows each step as it executes in real-time
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        "Streaming research workflow started",
        extra={"request_id": request_id}
    )
    
    async def event_generator():
        try:
            yield {
                "event": "start",
                "data": json.dumps({
                    "request_id": request_id,
                    "status": "Starting research workflow..."
                })
            }
            
            workflow = get_research_workflow()
            
            initial_state: ResearchState = {
                "query": research_request.query,
                "messages": [HumanMessage(content=research_request.query)],
                "documents_found": [],
                "web_results": None,
                "calculations": None,
                "research_plan": None,
                "final_answer": None,
                "iterations": 0,
                "needs_approval": False,
                "approved": None,
                "error": None
            }
            
            # Stream workflow execution
            async for event in workflow.astream(initial_state):
                for node_name, node_output in event.items():
                    yield {
                        "event": "step",
                        "data": json.dumps({
                            "step": node_name,
                            "output": {
                                "research_plan": node_output.get("research_plan", "")[:200] if node_output.get("research_plan") else None,
                                "documents_found": len(node_output.get("documents_found", [])),
                                "has_web_results": bool(node_output.get("web_results")),
                                "has_calculations": bool(node_output.get("calculations")),
                                "has_final_answer": bool(node_output.get("final_answer"))
                            }
                        })
                    }
            
            # Get final result
            result = await workflow.ainvoke(initial_state)
            
            yield {
                "event": "done",
                "data": json.dumps({
                    "request_id": request_id,
                    "final_answer": result.get("final_answer"),
                    "iterations": result.get("iterations", 0)
                })
            }
            
        except Exception as e:
            logger.error(
                f"Streaming workflow failed: {str(e)}",
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

@router.get("/workflows")
async def list_workflows(request: Request):
    """
    List available workflows
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    return {
        "workflows": [
            {
                "name": "research",
                "description": "Multi-step research with document search, web search, and calculations",
                "endpoint": "/api/graph/research",
                "features": ["document_search", "web_search", "calculations", "synthesis"]
            },
            {
                "name": "chat",
                "description": "Intelligent chat with automatic context retrieval",
                "endpoint": "/api/graph/chat",
                "features": ["query_analysis", "context_retrieval", "smart_routing"]
            }
        ],
        "request_id": request_id
    }