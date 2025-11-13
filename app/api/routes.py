from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
from app.logger import setup_logger
import os
import shutil
from datetime import datetime
from pathlib import Path

router = APIRouter(prefix="/api", tags=["documents"])
logger = setup_logger("docuchat.routes")

UPLOAD_DIR = "uploads"
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".doc", ".docx"}

def get_file_extension(filename: str) -> str:
    return Path(filename).suffix.lower()

def is_allowed_file(filename: str) -> bool:
    return get_file_extension(filename) in ALLOWED_EXTENSIONS

@router.post("/upload")
async def upload_document(request: Request, file: UploadFile = File(...)):
    """
    Upload a document (PDF, TXT, DOC, DOCX)
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        f"Upload request received for file: {file.filename}",
        extra={
            "request_id": request_id,
            "filename": file.filename,
            "content_type": file.content_type
        }
    )
    
    # Validate file type
    if not is_allowed_file(file.filename):
        logger.warning(
            f"Invalid file type attempted: {file.filename}",
            extra={
                "request_id": request_id,
                "filename": file.filename,
                "extension": get_file_extension(file.filename)
            }
        )
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Generate unique filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    original_name = Path(file.filename).stem
    extension = get_file_extension(file.filename)
    unique_filename = f"{original_name}_{timestamp}{extension}"
    
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    try:
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        logger.info(
            f"File uploaded successfully: {unique_filename}",
            extra={
                "request_id": request_id,
                "filename": unique_filename,
                "original_filename": file.filename,
                "size_bytes": file_size,
                "file_path": file_path
            }
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "File uploaded successfully",
                "filename": unique_filename,
                "original_filename": file.filename,
                "size_bytes": file_size,
                "size_mb": round(file_size / (1024 * 1024), 2),
                "upload_time": timestamp,
                "file_path": file_path,
                "request_id": request_id
            }
        )
    
    except Exception as e:
        logger.error(
            f"Failed to upload file: {str(e)}",
            extra={
                "request_id": request_id,
                "filename": file.filename,
                "error": str(e)
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload file: {str(e)}"
        )
    finally:
        file.file.close()

@router.get("/documents")
async def list_documents(request: Request):
    """
    List all uploaded documents
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info("Listing documents", extra={"request_id": request_id})
    
    try:
        files = []
        for filename in os.listdir(UPLOAD_DIR):
            file_path = os.path.join(UPLOAD_DIR, filename)
            if os.path.isfile(file_path):
                file_size = os.path.getsize(file_path)
                files.append({
                    "filename": filename,
                    "size_bytes": file_size,
                    "size_mb": round(file_size / (1024 * 1024), 2),
                    "extension": get_file_extension(filename)
                })
        
        logger.info(
            f"Found {len(files)} documents",
            extra={"request_id": request_id, "count": len(files)}
        )
        
        return {
            "total_documents": len(files),
            "documents": files
        }
    
    except Exception as e:
        logger.error(
            f"Failed to list documents: {str(e)}",
            extra={"request_id": request_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list documents: {str(e)}"
        )

@router.delete("/documents/{filename}")
async def delete_document(request: Request, filename: str):
    """
    Delete a specific document
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        f"Delete request for: {filename}",
        extra={"request_id": request_id, "filename": filename}
    )
    
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    if not os.path.exists(file_path):
        logger.warning(
            f"Document not found: {filename}",
            extra={"request_id": request_id, "filename": filename}
        )
        raise HTTPException(
            status_code=404,
            detail=f"Document '{filename}' not found"
        )
    
    try:
        os.remove(file_path)
        logger.info(
            f"Document deleted successfully: {filename}",
            extra={"request_id": request_id, "filename": filename}
        )
        return {
            "message": "Document deleted successfully",
            "filename": filename,
            "request_id": request_id
        }
    except Exception as e:
        logger.error(
            f"Failed to delete document: {str(e)}",
            extra={"request_id": request_id, "filename": filename, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {str(e)}"
        )