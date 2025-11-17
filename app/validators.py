"""
Input and output validators for guardrails
"""

from typing import Dict, List, Optional, Tuple
from app.logger import setup_logger
import re

logger = setup_logger("docuchat.validators")

class ValidationError(Exception):
    """Custom exception for validation failures"""
    pass

class InputValidator:
    """Validate user inputs"""
    
    # Banned patterns (injection attacks, etc.)
    BANNED_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # XSS
        r'javascript:',
        r'onerror\s*=',
        r'onload\s*=',
        r'DROP\s+TABLE',  # SQL injection
        r'DELETE\s+FROM',
        r'INSERT\s+INTO',
        r'--\s*$',  # SQL comments
        r'/\*.*?\*/',
        r'\.\./',  # Path traversal
    ]
    
    # Inappropriate content patterns
    INAPPROPRIATE_PATTERNS = [
        r'\b(hack|crack|exploit|malware|virus)\b',  # Security-related
        # Add more patterns as needed
    ]
    
    def __init__(self):
        self.banned_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.BANNED_PATTERNS]
        self.inappropriate_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.INAPPROPRIATE_PATTERNS]
    
    def validate_length(self, text: str, max_length: int = 10000, min_length: int = 1) -> Tuple[bool, Optional[str]]:
        """
        Validate text length
        
        Returns:
            (is_valid, error_message)
        """
        if len(text) < min_length:
            return False, f"Input too short (minimum {min_length} characters)"
        
        if len(text) > max_length:
            return False, f"Input too long (maximum {max_length} characters)"
        
        return True, None
    
    def detect_injection_attacks(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Detect potential injection attacks
        
        Returns:
            (is_safe, reason_if_unsafe)
        """
        for regex in self.banned_regex:
            if regex.search(text):
                logger.warning(
                    f"Potential injection attack detected",
                    extra={"pattern": regex.pattern}
                )
                return False, "Potentially malicious input detected"
        
        return True, None
    
    def check_inappropriate_content(self, text: str, strict: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Check for inappropriate content
        
        Args:
            text: Input text
            strict: If True, apply stricter checks
            
        Returns:
            (is_appropriate, reason_if_not)
        """
        for regex in self.inappropriate_regex:
            if regex.search(text):
                logger.warning(
                    f"Inappropriate content detected",
                    extra={"pattern": regex.pattern}
                )
                return False, "Content violates usage policy"
        
        return True, None
    
    def validate_query(
        self,
        query: str,
        max_length: int = 10000,
        check_injection: bool = True,
        check_inappropriate: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Comprehensive query validation
        
        Returns:
            (is_valid, error_message)
        """
        # Length check
        is_valid, error = self.validate_length(query, max_length)
        if not is_valid:
            return False, error
        
        # Injection attack check
        if check_injection:
            is_safe, error = self.detect_injection_attacks(query)
            if not is_safe:
                return False, error
        
        # Inappropriate content check
        if check_inappropriate:
            is_appropriate, error = self.check_inappropriate_content(query)
            if not is_appropriate:
                return False, error
        
        logger.debug(f"Query validation passed")
        return True, None

class OutputValidator:
    """Validate AI outputs"""
    
    def __init__(self):
        self.max_output_length = 50000  # 50K chars
    
    def validate_length(self, text: str) -> Tuple[bool, Optional[str]]:
        """Validate output length"""
        if len(text) > self.max_output_length:
            logger.warning(f"Output exceeds maximum length: {len(text)}")
            return False, "Output too long"
        return True, None
    
    def check_harmful_content(self, text: str) -> Tuple[bool, List[str]]:
        """
        Check for harmful content in outputs
        
        Returns:
            (is_safe, list_of_issues)
        """
        issues = []
        
        # Check for common harmful patterns
        harmful_patterns = {
            r'\b(password|secret|api[_-]?key)\s*[:=]\s*\S+': "Potential credential exposure",
            r'\bsudo\s+': "Potentially dangerous command",
            r'rm\s+-rf\s+/': "Dangerous system command",
        }
        
        for pattern, issue in harmful_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(issue)
                logger.warning(f"Harmful content detected: {issue}")
        
        return len(issues) == 0, issues
    
    def validate_output(self, text: str) -> Tuple[bool, Optional[str], List[str]]:
        """
        Comprehensive output validation
        
        Returns:
            (is_valid, error_message, warnings)
        """
        warnings = []
        
        # Length check
        is_valid, error = self.validate_length(text)
        if not is_valid:
            return False, error, warnings
        
        # Harmful content check
        is_safe, issues = self.check_harmful_content(text)
        if not is_safe:
            warnings.extend(issues)
            # Don't block, just warn
        
        return True, None, warnings

class TokenCounter:
    """Estimate and control token usage"""
    
    def __init__(self):
        # Rough estimation: 1 token ≈ 4 characters for English
        self.chars_per_token = 4
        self.max_tokens = 4000  # Default max
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate number of tokens in text"""
        return len(text) // self.chars_per_token
    
    def check_token_limit(self, text: str, max_tokens: Optional[int] = None) -> Tuple[bool, int]:
        """
        Check if text exceeds token limit
        
        Returns:
            (within_limit, estimated_tokens)
        """
        estimated = self.estimate_tokens(text)
        limit = max_tokens or self.max_tokens
        
        if estimated > limit:
            logger.warning(f"Token limit exceeded: {estimated} > {limit}")
            return False, estimated
        
        return True, estimated
    
    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token limit"""
        max_chars = max_tokens * self.chars_per_token
        if len(text) <= max_chars:
            return text
        
        truncated = text[:max_chars]
        logger.info(f"Text truncated from {len(text)} to {len(truncated)} chars")
        return truncated + "..."

# Global validator instances
input_validator = InputValidator()
output_validator = OutputValidator()
token_counter = TokenCounter()

def validate_input(
    query: str,
    max_length: int = 10000,
    check_injection: bool = True,
    check_inappropriate: bool = True
) -> None:
    """
    Validate input and raise ValidationError if invalid
    
    Args:
        query: User query to validate
        max_length: Maximum allowed length
        check_injection: Whether to check for injection attacks
        check_inappropriate: Whether to check for inappropriate content
        
    Raises:
        ValidationError: If validation fails
    """
    is_valid, error = input_validator.validate_query(
        query,
        max_length,
        check_injection,
        check_inappropriate
    )
    
    if not is_valid:
        raise ValidationError(error)

def validate_output(text: str) -> List[str]:
    """
    Validate output and return warnings
    
    Args:
        text: Output text to validate
        
    Returns:
        List of warning messages (empty if no issues)
        
    Raises:
        ValidationError: If output is invalid
    """
    is_valid, error, warnings = output_validator.validate_output(text)
    
    if not is_valid:
        raise ValidationError(error)
    
    return warnings