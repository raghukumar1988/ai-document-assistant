from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from app.api.loggers import get_logger, AppLogger
import os
import shutil
from datetime import datetime
from pathlib import Path

router = APIRouter(prefix="/api", tags=["documents"])

UPLOAD_DIR = "uploads"
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".doc", ".docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def get_request_logger(request: Request) -> AppLogger:
    """Dependency to inject logger with correlation ID"""
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')
    request_logger = get_logger(f"{__name__}.request")
    request_logger.set_correlation_id(correlation_id)
    return request_logger

def get_file_extension(filename: str) -> str:
    return Path(filename).suffix.lower()

def is_allowed_file(filename: str) -> bool:
    return get_file_extension(filename) in ALLOWED_EXTENSIONS

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    logger: AppLogger = Depends(get_request_logger)
):
    """
    Upload a document (PDF, TXT, DOC, DOCX)
    """
    logger.info(f"Document upload started: {file.filename}")
    
    try:
        # Validate file type
        if not is_allowed_file(file.filename):
            logger.warning(f"Invalid file type attempted: {file.filename}")
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # Read file content and check size
        content = await file.read()
        file_size = len(content)
        
        if file_size > MAX_FILE_SIZE:
            logger.warning(f"File too large: {file.filename} ({file_size} bytes)")
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # Generate unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        original_name = Path(file.filename).stem
        extension = get_file_extension(file.filename)
        unique_filename = f"{original_name}_{timestamp}{extension}"
        
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        logger.info(
            f"Document uploaded successfully: {file.filename} -> {unique_filename} "
            f"({file_size} bytes)"
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
                "file_path": file_path
            }
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions (already logged above)
        raise
    except Exception as e:
        logger.error(f"Document upload failed: {file.filename} - {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to upload file"
        )
    finally:
        # Ensure file handle is closed
        if hasattr(file, 'file') and file.file:
            file.file.close()

@router.get("/documents")
async def list_documents(logger: AppLogger = Depends(get_request_logger)):
    """
    List all uploaded documents
    """
    logger.info("Listing documents requested")
    
    try:
        if not os.path.exists(UPLOAD_DIR):
            logger.warning(f"Upload directory does not exist: {UPLOAD_DIR}")
            return {
                "total_documents": 0,
                "documents": []
            }
        
        files = []
        for filename in os.listdir(UPLOAD_DIR):
            file_path = os.path.join(UPLOAD_DIR, filename)
            if os.path.isfile(file_path):
                try:
                    file_size = os.path.getsize(file_path)
                    files.append({
                        "filename": filename,
                        "size_bytes": file_size,
                        "size_mb": round(file_size / (1024 * 1024), 2),
                        "extension": get_file_extension(filename),
                        "modified_date": datetime.fromtimestamp(
                            os.path.getmtime(file_path)
                        ).isoformat()
                    })
                except OSError as e:
                    logger.warning(f"Could not read file info for {filename}: {str(e)}")
                    continue
        
        logger.info(f"Documents listed successfully: {len(files)} files found")
        
        return {
            "total_documents": len(files),
            "documents": files
        }
    
    except Exception as e:
        logger.error(f"Failed to list documents: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to list documents"
        )

@router.delete("/documents/{filename}")
async def delete_document(
    filename: str,
    logger: AppLogger = Depends(get_request_logger)
):
    """
    Delete a specific document
    """
    logger.info(f"Document deletion requested: {filename}")
    
    try:
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        if not os.path.exists(file_path):
            logger.warning(f"Document not found for deletion: {filename}")
            raise HTTPException(
                status_code=404,
                detail=f"Document '{filename}' not found"
            )
        
        # Get file size before deletion for logging
        file_size = os.path.getsize(file_path)
        
        os.remove(file_path)
        
        logger.info(f"Document deleted successfully: {filename} ({file_size} bytes)")
        
        return {
            "message": "Document deleted successfully",
            "filename": filename
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions (already logged above)
        raise
    except Exception as e:
        logger.error(f"Failed to delete document {filename}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to delete document"
        )