from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import os
import shutil
from datetime import datetime
from pathlib import Path

router = APIRouter(prefix="/api", tags=["documents"])

UPLOAD_DIR = "uploads"
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".doc", ".docx"}

def get_file_extension(filename: str) -> str:
    return Path(filename).suffix.lower()

def is_allowed_file(filename: str) -> bool:
    return get_file_extension(filename) in ALLOWED_EXTENSIONS

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a document (PDF, TXT, DOC, DOCX)
    """
    # Validate file type
    if not is_allowed_file(file.filename):
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
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload file: {str(e)}"
        )
    finally:
        file.file.close()

@router.get("/documents")
async def list_documents():
    """
    List all uploaded documents
    """
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
        
        return {
            "total_documents": len(files),
            "documents": files
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list documents: {str(e)}"
        )

@router.delete("/documents/{filename}")
async def delete_document(filename: str):
    """
    Delete a specific document
    """
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail=f"Document '{filename}' not found"
        )
    
    try:
        os.remove(file_path)
        return {
            "message": "Document deleted successfully",
            "filename": filename
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {str(e)}"
        )