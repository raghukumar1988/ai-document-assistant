"""
PII (Personally Identifiable Information) detection and redaction
"""

from typing import List, Dict, Optional
from app.logger import setup_logger
import re

logger = setup_logger("docuchat.pii_detector")

try:
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine
    PRESIDIO_AVAILABLE = True
except ImportError:
    PRESIDIO_AVAILABLE = False
    logger.warning("Presidio not available - using regex-based PII detection")

class PIIDetector:
    """Detect and redact PII from text"""
    
    # Regex patterns for common PII
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    PHONE_PATTERN = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
    SSN_PATTERN = r'\b\d{3}-\d{2}-\d{4}\b'
    CREDIT_CARD_PATTERN = r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'
    
    def __init__(self):
        if PRESIDIO_AVAILABLE:
            try:
                self.analyzer = AnalyzerEngine()
                self.anonymizer = AnonymizerEngine()
                self.use_presidio = True
                logger.info("PII detector initialized with Presidio")
            except Exception as e:
                logger.warning(f"Failed to initialize Presidio: {str(e)}")
                self.use_presidio = False
        else:
            self.use_presidio = False
            logger.info("PII detector initialized with regex patterns")
    
    def detect_pii_regex(self, text: str) -> List[Dict[str, any]]:
        """
        Detect PII using regex patterns
        
        Returns:
            List of detected PII entities
        """
        entities = []
        
        # Email addresses
        for match in re.finditer(self.EMAIL_PATTERN, text):
            entities.append({
                "type": "EMAIL",
                "text": match.group(),
                "start": match.start(),
                "end": match.end(),
                "score": 0.9
            })
        
        # Phone numbers
        for match in re.finditer(self.PHONE_PATTERN, text):
            entities.append({
                "type": "PHONE_NUMBER",
                "text": match.group(),
                "start": match.start(),
                "end": match.end(),
                "score": 0.85
            })
        
        # SSN
        for match in re.finditer(self.SSN_PATTERN, text):
            entities.append({
                "type": "SSN",
                "text": match.group(),
                "start": match.start(),
                "end": match.end(),
                "score": 0.95
            })
        
        # Credit cards
        for match in re.finditer(self.CREDIT_CARD_PATTERN, text):
            entities.append({
                "type": "CREDIT_CARD",
                "text": match.group(),
                "start": match.start(),
                "end": match.end(),
                "score": 0.9
            })
        
        return entities
    
    def detect_pii_presidio(self, text: str) -> List[Dict[str, any]]:
        """
        Detect PII using Presidio
        
        Returns:
            List of detected PII entities
        """
        try:
            results = self.analyzer.analyze(
                text=text,
                language='en',
                entities=[
                    "EMAIL_ADDRESS",
                    "PHONE_NUMBER",
                    "PERSON",
                    "LOCATION",
                    "CREDIT_CARD",
                    "US_SSN",
                    "US_PASSPORT"
                ]
            )
            
            entities = []
            for result in results:
                entities.append({
                    "type": result.entity_type,
                    "text": text[result.start:result.end],
                    "start": result.start,
                    "end": result.end,
                    "score": result.score
                })
            
            return entities
            
        except Exception as e:
            logger.error(f"Presidio detection failed: {str(e)}")
            return self.detect_pii_regex(text)
    
    def detect_pii(self, text: str) -> List[Dict[str, any]]:
        """
        Detect PII in text
        
        Returns:
            List of detected PII entities
        """
        if self.use_presidio:
            entities = self.detect_pii_presidio(text)
        else:
            entities = self.detect_pii_regex(text)
        
        if entities:
            logger.info(
                f"Detected {len(entities)} PII entities",
                extra={
                    "count": len(entities),
                    "types": [e["type"] for e in entities]
                }
            )
        
        return entities
    
    def redact_pii(self, text: str, replacement: str = "[REDACTED]") -> str:
        """
        Redact PII from text
        
        Args:
            text: Original text
            replacement: Replacement string for PII
            
        Returns:
            Text with PII redacted
        """
        entities = self.detect_pii(text)
        
        if not entities:
            return text
        
        # Sort by position (reverse order to maintain indices)
        entities.sort(key=lambda x: x["start"], reverse=True)
        
        redacted_text = text
        for entity in entities:
            redacted_text = (
                redacted_text[:entity["start"]] +
                f"{replacement}_{entity['type']}" +
                redacted_text[entity["end"]:]
            )
        
        logger.info(f"Redacted {len(entities)} PII entities from text")
        return redacted_text
    
    def mask_pii(self, text: str, mask_char: str = "*") -> str:
        """
        Mask PII while keeping some context
        
        Args:
            text: Original text
            mask_char: Character to use for masking
            
        Returns:
            Text with PII masked
        """
        entities = self.detect_pii(text)
        
        if not entities:
            return text
        
        # Sort by position (reverse order)
        entities.sort(key=lambda x: x["start"], reverse=True)
        
        masked_text = text
        for entity in entities:
            original = entity["text"]
            
            if entity["type"] == "EMAIL":
                # Keep first char and domain: a***@example.com
                at_pos = original.find("@")
                if at_pos > 0:
                    masked = original[0] + mask_char * (at_pos - 1) + original[at_pos:]
                else:
                    masked = mask_char * len(original)
            
            elif entity["type"] in ["PHONE_NUMBER", "SSN"]:
                # Keep last 4 digits: ***-**-1234
                if len(original) > 4:
                    masked = mask_char * (len(original) - 4) + original[-4:]
                else:
                    masked = mask_char * len(original)
            
            elif entity["type"] == "CREDIT_CARD":
                # Keep last 4: **** **** **** 1234
                digits = re.sub(r'\D', '', original)
                if len(digits) > 4:
                    masked = mask_char * (len(digits) - 4) + digits[-4:]
                    # Restore formatting
                    masked = ' '.join([masked[i:i+4] for i in range(0, len(masked), 4)])
                else:
                    masked = mask_char * len(original)
            
            else:
                # Default: mask everything
                masked = mask_char * len(original)
            
            masked_text = (
                masked_text[:entity["start"]] +
                masked +
                masked_text[entity["end"]:]
            )
        
        return masked_text

# Global PII detector instance
pii_detector = PIIDetector()

def detect_pii(text: str) -> List[Dict[str, any]]:
    """Convenience function to detect PII"""
    return pii_detector.detect_pii(text)

def redact_pii(text: str) -> str:
    """Convenience function to redact PII"""
    return pii_detector.redact_pii(text)

def mask_pii(text: str) -> str:
    """Convenience function to mask PII"""
    return pii_detector.mask_pii(text)