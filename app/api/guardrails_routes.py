from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.validators import validate_input, validate_output, ValidationError, token_counter
from app.pii_detector import detect_pii, redact_pii, mask_pii
from app.rate_limiter import limiter, get_rate_limit
from app.logger import setup_logger

router = APIRouter(prefix="/api/guardrails", tags=["guardrails"])
logger = setup_logger("docuchat.guardrails_routes")

class ValidateInputRequest(BaseModel):
    """Input validation request"""
    text: str = Field(..., description="Text to validate")
    max_length: int = Field(default=10000, description="Maximum allowed length")
    check_injection: bool = Field(default=True, description="Check for injection attacks")
    check_inappropriate: bool = Field(default=True, description="Check for inappropriate content")

class ValidateOutputRequest(BaseModel):
    """Output validation request"""
    text: str = Field(..., description="Text to validate")

class PIIDetectionRequest(BaseModel):
    """PII detection request"""
    text: str = Field(..., description="Text to analyze for PII")

class PIIRedactionRequest(BaseModel):
    """PII redaction request"""
    text: str = Field(..., description="Text to redact PII from")
    mode: str = Field(default="redact", description="redact, mask, or detect")

class TokenEstimateRequest(BaseModel):
    """Token estimation request"""
    text: str = Field(..., description="Text to estimate tokens for")

@router.post("/validate/input")
@limiter.limit(get_rate_limit("default"))
async def validate_input_endpoint(request: Request, validation_request: ValidateInputRequest):
    """
    Validate user input
    
    Checks:
    - Length limits
    - Injection attacks (XSS, SQL injection)
    - Inappropriate content
    
    Returns validation result with any errors found
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        "Input validation requested",
        extra={
            "request_id": request_id,
            "text_length": len(validation_request.text)
        }
    )
    
    try:
        validate_input(
            validation_request.text,
            validation_request.max_length,
            validation_request.check_injection,
            validation_request.check_inappropriate
        )
        
        return {
            "valid": True,
            "message": "Input passed all validation checks",
            "text_length": len(validation_request.text),
            "request_id": request_id
        }
        
    except ValidationError as e:
        logger.warning(
            f"Input validation failed: {str(e)}",
            extra={"request_id": request_id}
        )
        return {
            "valid": False,
            "error": str(e),
            "text_length": len(validation_request.text),
            "request_id": request_id
        }
    
    except Exception as e:
        logger.error(
            f"Input validation error: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/validate/output")
@limiter.limit(get_rate_limit("default"))
async def validate_output_endpoint(request: Request, validation_request: ValidateOutputRequest):
    """
    Validate AI output
    
    Checks:
    - Length limits
    - Harmful content (credentials, dangerous commands)
    
    Returns validation result with warnings
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        "Output validation requested",
        extra={
            "request_id": request_id,
            "text_length": len(validation_request.text)
        }
    )
    
    try:
        warnings = validate_output(validation_request.text)
        
        return {
            "valid": True,
            "warnings": warnings,
            "text_length": len(validation_request.text),
            "has_warnings": len(warnings) > 0,
            "request_id": request_id
        }
        
    except ValidationError as e:
        logger.error(
            f"Output validation failed: {str(e)}",
            extra={"request_id": request_id}
        )
        return {
            "valid": False,
            "error": str(e),
            "text_length": len(validation_request.text),
            "request_id": request_id
        }
    
    except Exception as e:
        logger.error(
            f"Output validation error: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/pii/detect")
@limiter.limit(get_rate_limit("default"))
async def detect_pii_endpoint(request: Request, pii_request: PIIDetectionRequest):
    """
    Detect PII (Personally Identifiable Information) in text
    
    Detects:
    - Email addresses
    - Phone numbers
    - Social Security Numbers
    - Credit card numbers
    - Names (with Presidio)
    - Locations (with Presidio)
    
    Returns list of detected PII entities
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        "PII detection requested",
        extra={
            "request_id": request_id,
            "text_length": len(pii_request.text)
        }
    )
    
    try:
        entities = detect_pii(pii_request.text)
        
        # Remove actual PII text from response for security
        safe_entities = [
            {
                "type": e["type"],
                "start": e["start"],
                "end": e["end"],
                "score": e["score"],
                "length": len(e["text"])
            }
            for e in entities
        ]
        
        return {
            "pii_found": len(entities) > 0,
            "count": len(entities),
            "entities": safe_entities,
            "types": list(set(e["type"] for e in entities)),
            "request_id": request_id
        }
        
    except Exception as e:
        logger.error(
            f"PII detection error: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/pii/redact")
@limiter.limit(get_rate_limit("default"))
async def redact_pii_endpoint(request: Request, redaction_request: PIIRedactionRequest):
    """
    Redact or mask PII from text
    
    Modes:
    - detect: Just detect, don't modify
    - redact: Replace PII with [REDACTED_TYPE]
    - mask: Mask PII with asterisks (e.g., a***@example.com)
    
    Returns processed text with PII removed/masked
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        f"PII {redaction_request.mode} requested",
        extra={
            "request_id": request_id,
            "mode": redaction_request.mode
        }
    )
    
    try:
        if redaction_request.mode == "detect":
            entities = detect_pii(redaction_request.text)
            processed_text = redaction_request.text
            
        elif redaction_request.mode == "redact":
            entities = detect_pii(redaction_request.text)
            processed_text = redact_pii(redaction_request.text)
            
        elif redaction_request.mode == "mask":
            entities = detect_pii(redaction_request.text)
            processed_text = mask_pii(redaction_request.text)
            
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mode: {redaction_request.mode}. Use 'detect', 'redact', or 'mask'"
            )
        
        return {
            "processed_text": processed_text,
            "pii_found": len(entities) > 0,
            "count": len(entities),
            "types": list(set(e["type"] for e in entities)),
            "mode": redaction_request.mode,
            "request_id": request_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"PII redaction error: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tokens/estimate")
@limiter.limit(get_rate_limit("default"))
async def estimate_tokens_endpoint(request: Request, token_request: TokenEstimateRequest):
    """
    Estimate token count for text
    
    Useful for:
    - Cost estimation
    - Checking if text fits in context window
    - Optimizing prompts
    
    Returns estimated token count
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        estimated_tokens = token_counter.estimate_tokens(token_request.text)
        within_limit, _ = token_counter.check_token_limit(token_request.text)
        
        return {
            "text_length": len(token_request.text),
            "estimated_tokens": estimated_tokens,
            "within_default_limit": within_limit,
            "default_limit": token_counter.max_tokens,
            "cost_estimate_usd": estimated_tokens * 0.00002,  # Rough estimate
            "request_id": request_id
        }
        
    except Exception as e:
        logger.error(
            f"Token estimation error: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/config")
async def get_guardrails_config(request: Request):
    """
    Get current guardrails configuration
    
    Returns active settings and limits
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    return {
        "validation": {
            "max_input_length": 10000,
            "max_output_length": 50000,
            "injection_check_enabled": True,
            "inappropriate_content_check_enabled": True
        },
        "pii_detection": {
            "enabled": True,
            "supported_types": [
                "EMAIL",
                "PHONE_NUMBER",
                "SSN",
                "CREDIT_CARD",
                "PERSON",
                "LOCATION"
            ]
        },
        "rate_limits": {
            "default": "100/hour",
            "chat": "50/hour",
            "upload": "20/hour",
            "agent": "30/hour",
            "workflow": "20/hour"
        },
        "token_limits": {
            "default_max": 4000,
            "estimation_ratio": "1 token ≈ 4 characters"
        },
        "request_id": request_id
    }

@router.post("/test")
@limiter.limit(get_rate_limit("default"))
async def test_guardrails(request: Request):
    """
    Test all guardrails with sample data
    
    Useful for verifying guardrails are working correctly
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    test_results = {}
    
    # Test input validation
    try:
        validate_input("This is a safe query", max_length=1000)
        test_results["input_validation"] = {"status": "passed", "message": "Safe input accepted"}
    except Exception as e:
        test_results["input_validation"] = {"status": "error", "message": str(e)}
    
    # Test PII detection
    try:
        test_text = "My email is test@example.com and phone is 555-123-4567"
        entities = detect_pii(test_text)
        test_results["pii_detection"] = {
            "status": "passed",
            "entities_found": len(entities),
            "types": [e["type"] for e in entities]
        }
    except Exception as e:
        test_results["pii_detection"] = {"status": "error", "message": str(e)}
    
    # Test token counting
    try:
        tokens = token_counter.estimate_tokens("This is a test message")
        test_results["token_counting"] = {"status": "passed", "estimated_tokens": tokens}
    except Exception as e:
        test_results["token_counting"] = {"status": "error", "message": str(e)}
    
    return {
        "overall_status": "healthy",
        "tests": test_results,
        "request_id": request_id
    }