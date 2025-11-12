from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import routes
import os

# Create uploads directory if it doesn't exist
os.makedirs("uploads", exist_ok=True)

app = FastAPI(
    title="DocuChat API",
    description="Intelligent Document Assistant - Phase 1: Basic API",
    version="0.1.0"
)

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

@app.get("/")
async def root():
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
async def health_check():
    return {
        "status": "healthy",
        "service": "DocuChat API"
    }



# Start the development server
# uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000