from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, Field
from typing import Optional
from app.document_processor import document_processor
from app.vector_store import get_vector_store_service
from app.llm import get_llm_service
from app.logger import setup_logger
import json

router = APIRouter(prefix="/api/rag", tags=["rag-streaming"])
logger = setup_logger("docuchat.rag_stream")

class StreamingQuestionRequest(BaseModel):
    """Request for streaming RAG question"""
    question: str = Field(..., description="Question about documents", min_length=1)
    filename: Optional[str] = Field(None, description="Specific document to query")
    num_results: int = Field(default=4, description="Number of chunks to retrieve", ge=1, le=10)

@router.post("/ask/stream")
async def ask_question_stream(request: Request, question_request: StreamingQuestionRequest):
    """
    Ask a question about documents with streaming response
    
    Process:
    1. Search for relevant chunks (non-streaming)
    2. Send sources first
    3. Stream the AI answer generation
    
    Returns Server-Sent Events with:
    - 'sources' event: Relevant document chunks
    - 'message' events: Answer chunks as they generate
    - 'done' event: Completion signal
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        f"Streaming RAG question received",
        extra={
            "request_id": request_id,
            "question": question_request.question[:100],
        }
    )
    
    async def event_generator():
        try:
            # Send start event
            yield {
                "event": "start",
                "data": json.dumps({
                    "request_id": request_id,
                    "status": "searching"
                })
            }
            
            # Get vector store and search
            vector_store = get_vector_store_service()
            
            filter_metadata = None
            if question_request.filename:
                filter_metadata = {"filename": question_request.filename}
            
            # Search for relevant chunks
            results = vector_store.search_with_scores(
                query=question_request.question,
                k=question_request.num_results
            )
            
            if not results:
                yield {
                    "event": "error",
                    "data": json.dumps({
                        "error": "No relevant documents found",
                        "request_id": request_id
                    })
                }
                return
            
            # Send sources event
            sources = []
            context_parts = []
            
            for doc, score in results:
                source = {
                    "content": doc.page_content,
                    "filename": doc.metadata.get("filename", "unknown"),
                    "chunk_index": doc.metadata.get("chunk_index", 0),
                    "score": float(score) if score else None
                }
                sources.append(source)
                
                context_parts.append(
                    f"[Source: {doc.metadata.get('filename', 'unknown')}, "
                    f"Chunk {doc.metadata.get('chunk_index', 0)}]\n{doc.page_content}"
                )
            
            yield {
                "event": "sources",
                "data": json.dumps({
                    "sources": sources,
                    "num_sources": len(sources)
                })
            }
            
            logger.info(
                f"Found {len(sources)} relevant chunks, starting answer generation",
                extra={"request_id": request_id}
            )
            
            # Send status update
            yield {
                "event": "status",
                "data": json.dumps({
                    "status": "generating",
                    "message": "Generating answer based on retrieved context..."
                })
            }
            
            # Build context
            context = "\n\n---\n\n".join(context_parts)
            
            # Create RAG prompt
            rag_prompt = f"""You are a helpful assistant answering questions about documents.

Use the following document excerpts to answer the user's question. 
If the answer cannot be found in the provided context, say so clearly.
Always cite which source/chunk you're using when providing information.

DOCUMENT CONTEXT:
{context}

USER QUESTION: {question_request.question}

ANSWER:"""
            
            # Stream the answer
            llm_service = get_llm_service()
            full_response = ""
            
            async for chunk in llm_service.chat_stream(
                message=rag_prompt,
                system_prompt=(
                    "You are a helpful document assistant. Answer questions based on the provided "
                    "document context. Be specific and cite sources. If information is not in the "
                    "context, say you don't have that information in the documents."
                ),
                request_id=request_id
            ):
                full_response += chunk
                yield {
                    "event": "message",
                    "data": json.dumps({
                        "chunk": chunk,
                        "full_text": full_response
                    })
                }
            
            # Send completion
            yield {
                "event": "done",
                "data": json.dumps({
                    "request_id": request_id,
                    "status": "completed",
                    "full_response": full_response,
                    "num_sources": len(sources)
                })
            }
            
            logger.info(
                f"Streaming RAG completed",
                extra={
                    "request_id": request_id,
                    "response_length": len(full_response),
                    "num_sources": len(sources)
                }
            )
            
        except Exception as e:
            logger.error(
                f"Streaming RAG failed: {str(e)}",
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