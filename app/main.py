from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import routes
from app.api import chat_routes
from app.api import rag_routes
from app.api import rag_stream_routes
from app.api import agent_routes
from app.logger import setup_logger
from app.middleware import LoggingMiddleware, RequestBodyLoggingMiddleware
import os

# Setup logger
logger = setup_logger("docuchat.main")

# Create necessary directories
os.makedirs("uploads", exist_ok=True)
os.makedirs("chroma_db", exist_ok=True)
logger.info("Directories initialized")

app = FastAPI(
    title="DocuChat API",
    description="Intelligent Document Assistant - Phase 6: AI Agents with Tools",
    version="0.6.0"
)

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

@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {
        "message": "Welcome to DocuChat API",
        "version": "0.6.0",
        "phase": "Phase 6 - AI Agents with Tools",
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
            "agent_test": "/api/agent/test"
        }
    }

@app.get("/health")
async def health_check():
    logger.debug("Health check endpoint called")
    return {
        "status": "healthy",
        "service": "DocuChat API"
    }