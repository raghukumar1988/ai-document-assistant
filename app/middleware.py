from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message
import time
import uuid
from app.logger import setup_logger
import json

logger = setup_logger("docuchat.middleware")

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all requests and responses"""
    
    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Add request ID to request state (accessible in route handlers)
        request.state.request_id = request_id
        
        # Log request
        start_time = time.time()
        
        logger.info(
            f"Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "client_host": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            }
        )
        
        # Process request and catch any errors
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log response
            logger.info(
                f"Request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "url": str(request.url),
                    "status_code": response.status_code,
                    "process_time": f"{process_time:.3f}s",
                }
            )
            
            # Add custom headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.3f}s"
            
            return response
            
        except Exception as e:
            # Log error
            process_time = time.time() - start_time
            
            logger.error(
                f"Request failed with error: {str(e)}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "url": str(request.url),
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "process_time": f"{process_time:.3f}s",
                },
                exc_info=True
            )
            
            # Re-raise the exception to be handled by FastAPI
            raise

class RequestBodyLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log request bodies (be careful with sensitive data)"""
    
    async def set_body(self, request: Request):
        """Read and store the request body"""
        receive_ = await request._receive()
        
        async def receive() -> Message:
            return receive_
        
        request._receive = receive
    
    async def dispatch(self, request: Request, call_next):
        # Skip body logging for file uploads (too large)
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            
            # Only log JSON bodies
            if "application/json" in content_type:
                await self.set_body(request)
                body = await request.body()
                
                if body:
                    try:
                        body_json = json.loads(body.decode())
                        
                        logger.debug(
                            "Request body received",
                            extra={
                                "request_id": getattr(request.state, "request_id", "unknown"),
                                "body": body_json,
                                "content_type": content_type,
                            }
                        )
                    except Exception as e:
                        logger.warning(
                            f"Could not parse request body: {str(e)}",
                            extra={
                                "request_id": getattr(request.state, "request_id", "unknown"),
                            }
                        )
        
        response = await call_next(request)
        return response