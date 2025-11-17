from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api import routes
from app.api import chat_routes
from app.api import rag_routes
from app.api import rag_stream_routes
from app.api import agent_routes
from app.api import graph_routes
from app.api import guardrails_routes
from app.logger import setup_logger
from app.middleware import LoggingMiddleware, RequestBodyLoggingMiddleware
from app.rate_limiter import limiter, custom_rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import os

# Setup logger
logger = setup_logger("docuchat.main")

# Create necessary directories
os.makedirs("uploads", exist_ok=True)
os.makedirs("chroma_db", exist_ok=True)
logger.info("Directories initialized")

app = FastAPI(
    title="DocuChat API",
    description="Intelligent Document Assistant - Phase 8: Guardrails & Safety",
    version="0.8.0"
)

# Add rate limiter state
app.state.limiter = limiter

# Add exception handler for rate limit
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_exceeded_handler)

# Add logging middleware (order matters - add these first)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RequestBodyLoggingMiddleware)

# Add CORS middleware for frontend access later
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(routes.router)
app.include_router(chat_routes.router)
app.include_router(rag_routes.router)
app.include_router(rag_stream_routes.router)
app.include_router(agent_routes.router)
app.include_router(graph_routes.router)
app.include_router(guardrails_routes.router)

@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {
        "message": "Welcome to DocuChat API",
        "version": "0.8.0",
        "phase": "Phase 8 - Guardrails & Safety",
        "endpoints": {
            "health": "/health",
            "upload": "/api/upload",
            "documents": "/api/documents",
            "chat": "/api/chat",
            "chat_stream": "/api/chat/stream",
            "test_connection": "/api/chat/test",
            "process_document": "/api/rag/process",
            "ask_question": "/api/rag/ask",
            "ask_question_stream": "/api/rag/ask/stream",
            "processed_documents": "/api/rag/documents",
            "agent_tools": "/api/agent/tools",
            "agent_run": "/api/agent/run",
            "agent_stream": "/api/agent/stream",
            "agent_test": "/api/agent/test",
            "workflows": "/api/graph/workflows",
            "research_workflow": "/api/graph/research",
            "chat_workflow": "/api/graph/chat",
            "research_stream": "/api/graph/research/stream",
            "guardrails_config": "/api/guardrails/config",
            "validate_input": "/api/guardrails/validate/input",
            "validate_output": "/api/guardrails/validate/output",
            "detect_pii": "/api/guardrails/pii/detect",
            "redact_pii": "/api/guardrails/pii/redact",
            "estimate_tokens": "/api/guardrails/tokens/estimate",
            "test_guardrails": "/api/guardrails/test"
        }
    }

@app.get("/health")
async def health_check():
    logger.debug("Health check endpoint called")
    return {
        "status": "healthy",
        "service": "DocuChat API"
    }