"""
Rate limiting for API endpoints
"""

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from app.logger import setup_logger

logger = setup_logger("docuchat.rate_limiter")

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

def get_rate_limit_key(request: Request) -> str:
    """
    Get rate limit key from request
    Uses IP address by default, but can be customized
    """
    # Try to get user ID from auth headers (if implemented)
    user_id = request.headers.get("X-User-ID")
    if user_id:
        return f"user:{user_id}"
    
    # Fallback to IP address
    return get_remote_address(request)

def custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded"""
    logger.warning(
        f"Rate limit exceeded",
        extra={
            "ip": get_remote_address(request),
            "path": request.url.path,
            "limit": exc.detail
        }
    )
    
    return {
        "error": "Rate limit exceeded",
        "detail": "Too many requests. Please try again later.",
        "retry_after": "60 seconds"
    }

# Rate limit configurations
RATE_LIMITS = {
    "default": "100/hour",           # Default for most endpoints
    "chat": "50/hour",               # Chat endpoints
    "upload": "20/hour",             # File uploads
    "agent": "30/hour",              # Agent endpoints (expensive)
    "workflow": "20/hour",           # Workflow endpoints (expensive)
    "health": "1000/hour",           # Health checks (lenient)
}

def get_rate_limit(endpoint_type: str = "default") -> str:
    """Get rate limit string for endpoint type"""
    return RATE_LIMITS.get(endpoint_type, RATE_LIMITS["default"])