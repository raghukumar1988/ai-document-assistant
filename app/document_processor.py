from pypdf import PdfReader
from pathlib import Path
from typing import Optional
from app.logger import setup_logger

logger = setup_logger("docuchat.document_processor")

class DocumentProcessor:
    """Process and extract text from various document types"""
    
    def __init__(self):
        """Initialize document processor"""
        self.supported_extensions = {'.pdf', '.txt'}
    
    def extract_text(self, file_path: str) -> str:
        """
        Extract text from a document
        
        Args:
            file_path: Path to the document
            
        Returns:
            Extracted text as string
            
        Raises:
            ValueError: If file type is not supported
            Exception: If extraction fails
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        extension = path.suffix.lower()
        
        logger.info(
            f"Extracting text from document",
            extra={
                "file_path": file_path,
                "extension": extension,
                "file_size": path.stat().st_size
            }
        )
        
        try:
            if extension == '.pdf':
                text = self._extract_from_pdf(file_path)
            elif extension == '.txt':
                text = self._extract_from_txt(file_path)
            else:
                raise ValueError(
                    f"Unsupported file type: {extension}. "
                    f"Supported types: {', '.join(self.supported_extensions)}"
                )
            
            # Clean and validate extracted text
            text = text.strip()
            
            if not text:
                raise ValueError(f"No text extracted from document: {file_path}")
            
            logger.info(
                f"Text extracted successfully",
                extra={
                    "file_path": file_path,
                    "text_length": len(text),
                    "word_count": len(text.split())
                }
            )
            
            return text
            
        except Exception as e:
            logger.error(
                f"Failed to extract text: {str(e)}",
                extra={"file_path": file_path, "error": str(e)},
                exc_info=True
            )
            raise
    
    def _extract_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
        text_parts = []
        
        with open(file_path, 'rb') as file:
            pdf_reader = PdfReader(file)
            num_pages = len(pdf_reader.pages)
            
            logger.debug(
                f"Processing PDF with {num_pages} pages",
                extra={"file_path": file_path, "num_pages": num_pages}
            )
            
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                    
                    logger.debug(
                        f"Extracted text from page {page_num + 1}/{num_pages}",
                        extra={
                            "file_path": file_path,
                            "page_num": page_num + 1,
                            "page_text_length": len(page_text) if page_text else 0
                        }
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to extract text from page {page_num + 1}: {str(e)}",
                        extra={"file_path": file_path, "page_num": page_num + 1}
                    )
                    continue
        
        return "\n\n".join(text_parts)
    
    def _extract_from_txt(self, file_path: str) -> str:
        """Extract text from TXT file"""
        try:
            # Try UTF-8 first
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except UnicodeDecodeError:
            # Fallback to latin-1
            logger.warning(
                f"UTF-8 decoding failed, trying latin-1",
                extra={"file_path": file_path}
            )
            with open(file_path, 'r', encoding='latin-1') as file:
                return file.read()
    
    def get_document_metadata(self, file_path: str) -> dict:
        """
        Get metadata about a document
        
        Args:
            file_path: Path to the document
            
        Returns:
            Dictionary with metadata
        """
        path = Path(file_path)
        
        metadata = {
            "filename": path.name,
            "extension": path.suffix.lower(),
            "size_bytes": path.stat().st_size,
            "size_mb": round(path.stat().st_size / (1024 * 1024), 2),
        }
        
        # Add PDF-specific metadata
        if path.suffix.lower() == '.pdf':
            try:
                with open(file_path, 'rb') as file:
                    pdf_reader = PdfReader(file)
                    metadata["num_pages"] = len(pdf_reader.pages)
                    
                    # Extract PDF metadata if available
                    if pdf_reader.metadata:
                        pdf_meta = pdf_reader.metadata
                        metadata["title"] = pdf_meta.get('/Title', '')
                        metadata["author"] = pdf_meta.get('/Author', '')
                        metadata["subject"] = pdf_meta.get('/Subject', '')
                        metadata["creator"] = pdf_meta.get('/Creator', '')
            except Exception as e:
                logger.warning(
                    f"Failed to extract PDF metadata: {str(e)}",
                    extra={"file_path": file_path}
                )
        
        return metadata

# Global document processor instance
document_processor = DocumentProcessor()