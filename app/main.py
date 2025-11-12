import time
from datetime import datetime
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.api import routes
from app.api.loggers import get_logger, generate_correlation_id, AppLogger
import os

# Create uploads directory if it doesn't exist
os.makedirs("uploads", exist_ok=True)

app = FastAPI(
    title="DocuChat API",
    description="Intelligent Document Assistant - Phase 1: Basic API",
    version="0.1.0"
)

# Get logger for main module
logger = get_logger(__name__)

# Add CORS middleware for frontend access later
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Add correlation ID and request logging"""
    correlation_id = generate_correlation_id()
    
    # Add correlation ID to request state
    request.state.correlation_id = correlation_id
    
    # Set correlation ID for logger
    logger.set_correlation_id(correlation_id)
    
    start_time = time.time()
    
    logger.info(f"Request started: {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    
    logger.info(
        f"Request completed: {request.method} {request.url.path} - "
        f"Status: {response.status_code} - Duration: {process_time:.3f}s"
    )
    
    return response

def get_request_logger(request: Request) -> AppLogger:
    """Dependency to inject logger with correlation ID"""
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')
    request_logger = get_logger(f"{__name__}.request")
    request_logger.set_correlation_id(correlation_id)
    return request_logger

# Include routes
app.include_router(routes.router)

@app.get("/")
async def root(logger: AppLogger = Depends(get_request_logger)):
    logger.info("Root endpoint accessed")
    
    return {
        "message": "Welcome to DocuChat API",
        "version": "0.1.0",
        "phase": "Phase 1 - FastAPI Foundation",
        "endpoints": {
            "health": "/health",
            "upload": "/api/upload",
            "documents": "/api/documents"
        }
    }

@app.get("/health")
async def health_check(logger: AppLogger = Depends(get_request_logger)):
    logger.info("Health check performed")
    
    return {
        "status": "healthy",
        "service": "DocuChat API",
        "timestamp": datetime.now().isoformat()
    }

# Start the development server
# uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000



# Start the development server
# uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000