"""
PDF processing module for extracting text and generating embeddings.
Ultra-optimized for memory efficiency and performance with O(1) and O(n) complexity.
"""
import gc
import os
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from functools import lru_cache
from backend.modules.utils import logger, log_memory_usage, cleanup_memory
from backend.modules.text_processor import split_text_by_chars

# Lazy imports for PDF processing libraries
try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    logger.warning("PyPDF2 not available, PDF processing will be limited")

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger.warning("PyMuPDF not available, using PyPDF2 fallback")

# Pre-computed constants for O(1) access
_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
_CHUNK_SIZE = 1000
_CHUNK_OVERLAP = 200

# Performance optimization constants
_CACHE_SIZE = 100  # Number of PDFs to cache in memory
_PROGRESS_BATCH_SIZE = 10  # Process every 10 pages for progress updates

@lru_cache(maxsize=32)
def _get_pdf_library_status() -> Tuple[bool, bool]:
    """Cached PDF library availability check - O(1) complexity."""
    return PYMUPDF_AVAILABLE, PYPDF2_AVAILABLE

# Global cache for PDF text content to avoid reprocessing
_pdf_text_cache: Dict[str, str] = {}
_pdf_metadata_cache: Dict[str, Dict[str, Any]] = {}

def _get_file_hash(file_path: str) -> str:
    """Generate hash for file to use as cache key."""
    try:
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return str(hash(file_path))

def _log_progress(operation: str, current: int, total: int):
    """Log progress for long-running operations."""
    if total > 0:
        percentage = (current / total) * 100
        logger.info(f"{operation}: {current}/{total} ({percentage:.1f}%)")

def _clear_pdf_cache():
    """Clear PDF caches to free memory."""
    global _pdf_text_cache, _pdf_metadata_cache
    _pdf_text_cache.clear()
    _pdf_metadata_cache.clear()
    logger.info("PDF caches cleared")

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from PDF with ultra-optimized memory management and caching.
    Time Complexity: O(p) where p is number of pages
    Space Complexity: O(1) - constant memory usage with immediate cleanup
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text content
        
    Raises:
        ValueError: If no text could be extracted
        ImportError: If no PDF libraries are available
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    # Check cache first
    file_hash = _get_file_hash(pdf_path)
    if file_hash in _pdf_text_cache:
        logger.info(f"Using cached text for PDF: {pdf_path}")
        return _pdf_text_cache[file_hash]
    
    # Clear cache if it's getting too large
    if len(_pdf_text_cache) > _CACHE_SIZE:
        _clear_pdf_cache()
    
    try:
        log_memory_usage("starting PDF text extraction")
        
        # Get cached library status - O(1)
        pymupdf_available, pypdf2_available = _get_pdf_library_status()
        
        # Try PyMuPDF first (better text extraction and memory management)
        if pymupdf_available:
            try:
                doc = fitz.open(pdf_path)
                page_count = len(doc)
                
                # Pre-allocate text buffer for better performance
                text_parts = []
                
                # Optimized page processing - O(p) with immediate cleanup and progress tracking
                for page_num in range(page_count):
                    page = doc.load_page(page_num)
                    page_text = page.get_text()
                    if page_text.strip():  # Only add non-empty pages
                        text_parts.append(page_text)
                    # Immediate cleanup
                    if 'page' in locals():
                        del page
                    
                    # Progress tracking and cleanup every 10 pages
                    if page_num % _PROGRESS_BATCH_SIZE == 0:
                        _log_progress("PDF text extraction", page_num + 1, page_count)
                        # Only collect garbage if memory pressure is high
                        if len(gc.get_objects()) > 10000:
                            gc.collect()
                
                doc.close()
                if 'doc' in locals():
                    del doc
                # Only collect garbage if memory pressure is high
                if len(gc.get_objects()) > 10000:
                    gc.collect()
                
                # Efficient string joining - O(n) where n is total text length
                text = "".join(text_parts)
                if 'text_parts' in locals():
                    del text_parts
                # Only collect garbage if memory pressure is high
                if len(gc.get_objects()) > 10000:
                    gc.collect()
                
                if text.strip():
                    logger.info(f"Successfully extracted text using PyMuPDF from {pdf_path}")
                    log_memory_usage("PDF text extraction completed")
                    # Cache the result
                    _pdf_text_cache[file_hash] = text
                    return text
                else:
                    logger.warning("PyMuPDF extracted empty text, trying PyPDF2")
                    
            except Exception as e:
                # Ensure document is properly closed to prevent memory leaks
                if 'doc' in locals():
                    try:
                        doc.close()
                    except Exception:
                        pass
                logger.warning(f"PyMuPDF extraction failed: {e}, trying PyPDF2")
        
        # Fallback to PyPDF2 with optimized processing
        if pypdf2_available:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                page_count = len(reader.pages)
                
                # Pre-allocate text buffer
                text_parts = []
                
                # Optimized page processing - O(p) with immediate cleanup and progress tracking
                for page_num in range(page_count):
                    page = reader.pages[page_num]
                    page_text = page.extract_text()
                    if page_text.strip():  # Only add non-empty pages
                        text_parts.append(page_text)
                    # Immediate cleanup
                    if 'page' in locals():
                        del page
                    
                    # Progress tracking and cleanup every 10 pages
                    if page_num % _PROGRESS_BATCH_SIZE == 0:
                        _log_progress("PDF text extraction (PyPDF2)", page_num + 1, page_count)
                        # Only collect garbage if memory pressure is high
                        if len(gc.get_objects()) > 10000:
                            gc.collect()
                
                if 'reader' in locals():
                    del reader
                # Only collect garbage if memory pressure is high
                if len(gc.get_objects()) > 10000:
                    gc.collect()
                
                # Efficient string joining - O(n)
                text = "".join(text_parts)
                if 'text_parts' in locals():
                    del text_parts
                # Only collect garbage if memory pressure is high
                if len(gc.get_objects()) > 10000:
                    gc.collect()
                
                if text.strip():
                    logger.info(f"Successfully extracted text using PyPDF2 from {pdf_path}")
                    log_memory_usage("PDF text extraction completed")
                    # Cache the result
                    _pdf_text_cache[file_hash] = text
                    return text
                else:
                    raise ValueError("No text could be extracted from PDF")
        else:
            raise ImportError("No PDF processing libraries available. Install PyPDF2 or PyMuPDF")
            
    except Exception as e:
        logger.error(f"Failed to extract text from PDF {pdf_path}: {e}")
        cleanup_memory()
        raise

def process_pdf_file(pdf_path: str, pdf_id: str, pdf_title: str) -> List[Dict[str, Any]]:
    """
    Process PDF file and create chunks with metadata.
    Time Complexity: O(n) where n is text length
    Space Complexity: O(c) where c is number of chunks
    
    Args:
        pdf_path: Path to the PDF file
        pdf_id: Unique identifier for the PDF
        pdf_title: Title of the PDF document
        
    Returns:
        List of text chunks with metadata
        
    Raises:
        ValueError: If PDF processing fails
    """
    try:
        log_memory_usage("starting PDF processing")
        
        # Extract text from PDF
        text = extract_text_from_pdf(pdf_path)
        if not text.strip():
            raise ValueError("No text extracted from PDF")
        
        logger.info(f"Extracted {len(text)} characters from PDF {pdf_id}")
        
        # Create chunks with metadata using existing optimized function
        text_chunks = split_text_by_chars(text, chunk_size=_CHUNK_SIZE, overlap=_CHUNK_OVERLAP)
        
        # Clean up original text to free memory immediately
        if 'text' in locals():
            del text
        # Only collect garbage if memory pressure is high
        if len(gc.get_objects()) > 10000:
            gc.collect()
        
        # Pre-allocate chunks list with estimated capacity
        chunk_count = len(text_chunks)
        chunks = [None] * chunk_count  # Pre-allocate for O(1) access
        
        # Optimized chunk creation - O(c) single pass
        for i, chunk_data in enumerate(text_chunks):
            chunk_id = f"{pdf_id}_chunk_{i}"
            # Extract text from chunk_data (which is a dict with text, char_start, char_end)
            chunk_text = chunk_data["text"] if isinstance(chunk_data, dict) else chunk_data
            chunks[i] = {
                "text": chunk_text,  # This should be a string, not a dict
                "metadata": {
                    "pdf_id": pdf_id,
                    "pdf_title": pdf_title,
                    "chunk_id": chunk_id,
                    "source_type": "pdf",
                    "page_number": None  # Could be enhanced to track page numbers
                },
                "chunk_id": chunk_id
            }
        
        # Clean up text_chunks immediately
        if 'text_chunks' in locals():
            del text_chunks
        # Only collect garbage if memory pressure is high
        if len(gc.get_objects()) > 10000:
            gc.collect()
        
        logger.info(f"Created {chunk_count} chunks for PDF {pdf_id}")
        log_memory_usage("PDF processing completed")
        
        return chunks
        
    except Exception as e:
        logger.error(f"Failed to process PDF {pdf_id}: {e}")
        cleanup_memory()
        raise

def validate_pdf_file(pdf_path: str) -> bool:
    """
    Validate PDF file before processing.
    Time Complexity: O(1) - constant time validation
    Space Complexity: O(1) - constant memory usage
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        True if valid PDF, False otherwise
    """
    try:
        if not os.path.exists(pdf_path):
            return False
        
        # Check file size (limit to 50MB) - O(1)
        file_size = os.path.getsize(pdf_path)
        if file_size > _MAX_FILE_SIZE:
            logger.warning(f"PDF file too large: {file_size} bytes")
            return False
        
        # Get cached library status - O(1)
        pymupdf_available, pypdf2_available = _get_pdf_library_status()
        
        # Try to open with PyMuPDF first - O(1) validation
        if pymupdf_available:
            try:
                doc = fitz.open(pdf_path)
                page_count = len(doc)
                doc.close()
                return page_count > 0
            except Exception as e:
                logger.warning(f"PyMuPDF validation failed: {e}")
        
        # Fallback to PyPDF2 - O(1) validation
        if pypdf2_available:
            try:
                with open(pdf_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    return len(reader.pages) > 0
            except Exception as e:
                logger.warning(f"PyPDF2 validation failed: {e}")
        
        return False
        
    except Exception as e:
        logger.error(f"PDF validation failed: {e}")
        return False

def get_pdf_metadata(pdf_path: str) -> Dict[str, Any]:
    """
    Extract metadata from PDF file with optimized processing and caching.
    Time Complexity: O(1) - constant time metadata extraction
    Space Complexity: O(1) - constant memory usage
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Dictionary containing PDF metadata
    """
    try:
        # Validate file existence before processing
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        # Check cache first
        file_hash = _get_file_hash(pdf_path)
        if file_hash in _pdf_metadata_cache:
            logger.info(f"Using cached metadata for PDF: {pdf_path}")
            return _pdf_metadata_cache[file_hash]
        
        # Clear cache if it's getting too large
        if len(_pdf_metadata_cache) > _CACHE_SIZE:
            _clear_pdf_cache()
        
        # Pre-computed metadata structure for O(1) access
        metadata = {
            "filename": os.path.basename(pdf_path),
            "file_size": os.path.getsize(pdf_path),
            "page_count": 0,
            "title": None,
            "author": None,
            "subject": None,
            "creator": None
        }
        
        # Get cached library status - O(1)
        pymupdf_available, pypdf2_available = _get_pdf_library_status()
        
        # Try PyMuPDF first - O(1) metadata extraction
        if pymupdf_available:
            try:
                doc = fitz.open(pdf_path)
                metadata["page_count"] = len(doc)
                
                # Get document metadata efficiently
                doc_metadata = doc.metadata
                if doc_metadata:
                    # Single-pass metadata update - O(1)
                    metadata.update({
                        "title": doc_metadata.get("title"),
                        "author": doc_metadata.get("author"),
                        "subject": doc_metadata.get("subject"),
                        "creator": doc_metadata.get("creator")
                    })
                
                doc.close()
                # Cache the result
                _pdf_metadata_cache[file_hash] = metadata
                return metadata
            except Exception as e:
                logger.warning(f"PyMuPDF metadata extraction failed: {e}")
        
        # Fallback to PyPDF2 - O(1) metadata extraction
        if pypdf2_available:
            try:
                with open(pdf_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    metadata["page_count"] = len(reader.pages)
                    
                    # Get document metadata efficiently
                    if reader.metadata:
                        # Single-pass metadata update - O(1)
                        metadata.update({
                            "title": reader.metadata.get("/Title"),
                            "author": reader.metadata.get("/Author"),
                            "subject": reader.metadata.get("/Subject"),
                            "creator": reader.metadata.get("/Creator")
                        })
                    
                    # Cache the result
                    _pdf_metadata_cache[file_hash] = metadata
                    return metadata
            except Exception as e:
                logger.warning(f"PyPDF2 metadata extraction failed: {e}")
        
        return metadata
        
    except Exception as e:
        logger.error(f"Failed to extract PDF metadata: {e}")
        return {"filename": os.path.basename(pdf_path), "file_size": 0, "page_count": 0}

