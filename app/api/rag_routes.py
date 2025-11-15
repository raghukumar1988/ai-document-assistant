from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import List, Optional
from app.document_processor import document_processor
from app.vector_store import get_vector_store_service
from app.llm import get_llm_service
from app.logger import setup_logger
import os

router = APIRouter(prefix="/api/rag", tags=["rag"])
logger = setup_logger("docuchat.rag_routes")

UPLOAD_DIR = "uploads"

class ProcessDocumentRequest(BaseModel):
    """Request to process a document"""
    filename: str = Field(..., description="Filename in uploads directory")

class ProcessDocumentResponse(BaseModel):
    """Response after processing document"""
    success: bool
    filename: str
    num_chunks: int
    message: str
    request_id: str

class DocumentQuestionRequest(BaseModel):
    """Request to ask a question about documents"""
    question: str = Field(..., description="Question about the documents", min_length=1)
    filename: Optional[str] = Field(None, description="Specific document to query (optional)")
    num_results: int = Field(default=4, description="Number of relevant chunks to retrieve", ge=1, le=10)

class SourceChunk(BaseModel):
    """Source chunk from document"""
    content: str
    filename: str
    chunk_index: int
    score: Optional[float] = None

class DocumentQuestionResponse(BaseModel):
    """Response to document question"""
    answer: str
    sources: List[SourceChunk]
    num_sources: int
    request_id: str

@router.post("/process", response_model=ProcessDocumentResponse)
async def process_document(request: Request, process_request: ProcessDocumentRequest):
    """
    Process a document and add it to the vector store
    
    Steps:
    1. Extract text from document
    2. Chunk the text
    3. Create embeddings
    4. Store in vector database
    """
    request_id = getattr(request.state, "request_id", "unknown")
    filename = process_request.filename
    
    logger.info(
        f"Processing document for RAG",
        extra={"request_id": request_id, "uploaded_filename": filename}
    )
    
    # Check if file exists
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        logger.error(
            f"File not found: {filename}",
            extra={"request_id": request_id, "filename": filename}
        )
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    
    try:
        # Extract text from document
        text = document_processor.extract_text(file_path)
        
        # Get document metadata
        metadata = document_processor.get_document_metadata(file_path)
        metadata["filename"] = filename  # Ensure filename is in metadata
        
        # Add to vector store
        vector_store = get_vector_store_service()
        result = vector_store.add_document(text, metadata)
        
        logger.info(
            f"Document processed successfully",
            extra={
                "request_id": request_id,
                "uploaded_filename": filename,
                "num_chunks": result["num_chunks"]
            }
        )
        
        return ProcessDocumentResponse(
            success=True,
            filename=filename,
            num_chunks=result["num_chunks"],
            message=f"Document processed successfully. Created {result['num_chunks']} chunks.",
            request_id=request_id
        )
        
    except ValueError as e:
        logger.error(
            f"Document processing failed: {str(e)}",
            extra={"request_id": request_id, "uploaded_filename": filename},
            exc_info=True
        )
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(
            f"Document processing failed: {str(e)}",
            extra={"request_id": request_id, "uploaded_filename": filename},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process document: {str(e)}"
        )

@router.post("/ask", response_model=DocumentQuestionResponse)
async def ask_question(request: Request, question_request: DocumentQuestionRequest):
    """
    Ask a question about your documents using RAG
    
    The system will:
    1. Search for relevant document chunks
    2. Use them as context
    3. Generate an answer using Azure OpenAI
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        f"RAG question received",
        extra={
            "request_id": request_id,
            "question": question_request.question[:100],
            "filename_filter": question_request.filename,
            "num_results": question_request.num_results
        }
    )
    
    try:
        # Get vector store and search for relevant chunks
        vector_store = get_vector_store_service()
        
        # Build metadata filter if filename specified
        filter_metadata = None
        if question_request.filename:
            filter_metadata = {"filename": question_request.filename}
        
        # Search with scores to show relevance
        results = vector_store.search_with_scores(
            query=question_request.question,
            k=question_request.num_results
        )
        
        if not results:
            logger.warning(
                f"No relevant documents found",
                extra={"request_id": request_id, "question": question_request.question[:100]}
            )
            raise HTTPException(
                status_code=404,
                detail="No relevant documents found. Please process documents first using /api/rag/process"
            )
        
        # Format sources for response
        sources = []
        context_parts = []
        
        for doc, score in results:
            sources.append(SourceChunk(
                content=doc.page_content,
                filename=doc.metadata.get("filename", "unknown"),
                chunk_index=doc.metadata.get("chunk_index", 0),
                score=float(score) if score else None
            ))
            
            # Build context for LLM
            context_parts.append(
                f"[Source: {doc.metadata.get('filename', 'unknown')}, "
                f"Chunk {doc.metadata.get('chunk_index', 0)}]\n{doc.page_content}"
            )
        
        context = "\n\n---\n\n".join(context_parts)
        
        logger.info(
            f"Found {len(sources)} relevant chunks",
            extra={
                "request_id": request_id,
                "num_sources": len(sources),
                "context_length": len(context)
            }
        )
        
        # Create RAG prompt
        rag_prompt = f"""You are a helpful assistant answering questions about documents.

Use the following document excerpts to answer the user's question. 
If the answer cannot be found in the provided context, say so clearly.
Always cite which source/chunk you're using when providing information.

DOCUMENT CONTEXT:
{context}

USER QUESTION: {question_request.question}

ANSWER:"""
        
        # Get answer from LLM
        llm_service = get_llm_service()
        answer = await llm_service.chat(
            message=rag_prompt,
            system_prompt=(
                "You are a helpful document assistant. Answer questions based on the provided "
                "document context. Be specific and cite sources. If information is not in the "
                "context, say you don't have that information in the documents."
            ),
            request_id=request_id
        )
        
        logger.info(
            f"RAG answer generated",
            extra={
                "request_id": request_id,
                "answer_length": len(answer),
                "num_sources": len(sources)
            }
        )
        
        return DocumentQuestionResponse(
            answer=answer,
            sources=sources,
            num_sources=len(sources),
            request_id=request_id
        )
        
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(
            f"RAG question failed: {str(e)}",
            extra={"request_id": request_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process question: {str(e)}"
        )

@router.get("/documents")
async def list_processed_documents(request: Request):
    """
    List all documents that have been processed and are in the vector store
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info("Listing processed documents", extra={"request_id": request_id})
    
    try:
        vector_store = get_vector_store_service()
        documents = vector_store.list_documents()
        
        return {
            "total_documents": len(documents),
            "documents": documents,
            "request_id": request_id
        }
        
    except Exception as e:
        logger.error(
            f"Failed to list documents: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list documents: {str(e)}"
        )

@router.delete("/documents/{filename}")
async def delete_processed_document(request: Request, filename: str):
    """
    Delete a document from the vector store
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        f"Deleting processed document",
        extra={"request_id": request_id, "filename": filename}
    )
    
    try:
        vector_store = get_vector_store_service()
        vector_store.delete_document(filename)
        
        return {
            "success": True,
            "message": f"Document '{filename}' deleted from vector store",
            "filename": filename,
            "request_id": request_id
        }
        
    except Exception as e:
        logger.error(
            f"Failed to delete document: {str(e)}",
            extra={"request_id": request_id, "filename": filename},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {str(e)}"
        )