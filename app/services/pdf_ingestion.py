"""
Shared PDF ingestion service - single source of truth for PDF processing pipeline.
Eliminates duplication across pdf_ingest.py and auto_update_embeddings.py.
"""
import os
import hashlib
import uuid
import tempfile
from pathlib import Path
from typing import Dict, Optional, Tuple, Union
from app.utils.logger import logger, log_memory_usage, cleanup_memory, check_memory_threshold
from app.services.pdf_processor import process_pdf_file, validate_pdf_file, get_pdf_metadata
from app.services.pdf_store import store_pdf_embeddings, check_duplicate_pdf, delete_pdf_embeddings


class PDFIngestResult:
    """Result of PDF ingestion pipeline."""
    def __init__(
        self,
        pdf_id: str,
        filename: str,
        chunks_processed: int,
        embeddings_stored: int,
        processing_time: float,
        status: str,
        success: bool,
        error: Optional[str] = None
    ):
        self.pdf_id = pdf_id
        self.filename = filename
        self.chunks_processed = chunks_processed
        self.embeddings_stored = embeddings_stored
        self.processing_time = processing_time
        self.status = status
        self.success = success
        self.error = error


def generate_pdf_id_from_content(content: bytes) -> str:
    """
    Generate stable PDF ID from file content hash.
    This ensures the same PDF always gets the same ID, enabling duplicate detection.
    
    Args:
        content: PDF file content bytes
        
    Returns:
        Stable PDF ID string (format: pdf_<hash>)
    """
    file_hash = hashlib.md5(content).hexdigest()[:12]
    return f"pdf_{file_hash}"


def run_pdf_ingestion_from_path(
    pdf_path: str,
    pdf_id: Optional[str] = None,
    pdf_title: Optional[str] = None,
    force_reprocess: bool = False
) -> PDFIngestResult:
    """
    Single source of truth for PDF ingestion pipeline from file path.
    
    This function consolidates the PDF ingestion logic that was duplicated in:
    - app/api/routes/pdf_ingest.py::ingest_pdf()
    - auto_update_embeddings.py::process_pdf()
    
    Args:
        pdf_path: Path to PDF file
        pdf_id: Optional PDF ID (if None, generates from file hash)
        pdf_title: Optional PDF title (if None, uses filename stem)
        force_reprocess: Whether to reprocess if PDF already exists
        
    Returns:
        PDFIngestResult with processing details
    """
    import time
    start_time = time.time()
    
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before PDF processing")
        cleanup_memory()
    
    try:
        # Validate file exists
        if not os.path.exists(pdf_path):
            return PDFIngestResult(
                pdf_id=pdf_id or "unknown",
                filename=os.path.basename(pdf_path),
                chunks_processed=0,
                embeddings_stored=0,
                processing_time=time.time() - start_time,
                status="error",
                success=False,
                error=f"PDF file not found: {pdf_path}"
            )
        
        # Generate PDF ID from content if not provided
        if pdf_id is None:
            try:
                with open(pdf_path, 'rb') as f:
                    content = f.read()
                pdf_id = generate_pdf_id_from_content(content)
            except Exception as e:
                logger.error(f"Failed to generate PDF ID: {e}")
                pdf_id = str(uuid.uuid4())  # Fallback to UUID
        
        # Use filename stem as title if not provided
        if pdf_title is None:
            pdf_title = Path(pdf_path).stem
        
        # Validate PDF file
        if not validate_pdf_file(pdf_path):
            return PDFIngestResult(
                pdf_id=pdf_id,
                filename=os.path.basename(pdf_path),
                chunks_processed=0,
                embeddings_stored=0,
                processing_time=time.time() - start_time,
                status="error",
                success=False,
                error="Invalid or corrupted PDF file"
            )
        
        # Check for duplicates
        if not force_reprocess and check_duplicate_pdf(pdf_id):
            logger.info(f"PDF {pdf_id} already exists, skipping processing")
            return PDFIngestResult(
                pdf_id=pdf_id,
                filename=os.path.basename(pdf_path),
                chunks_processed=0,
                embeddings_stored=0,
                processing_time=time.time() - start_time,
                status="duplicate_skipped",
                success=True
            )
        
        # Get PDF metadata
        metadata = get_pdf_metadata(pdf_path)
        logger.info(f"Processing PDF: {os.path.basename(pdf_path)} ({metadata.get('page_count', 0)} pages)")
        
        # Process PDF file
        log_memory_usage("starting PDF processing")
        chunks = process_pdf_file(pdf_path, pdf_id, pdf_title)
        
        if not chunks:
            return PDFIngestResult(
                pdf_id=pdf_id,
                filename=os.path.basename(pdf_path),
                chunks_processed=0,
                embeddings_stored=0,
                processing_time=time.time() - start_time,
                status="error",
                success=False,
                error="No text content found in PDF"
            )
        
        # Store embeddings
        log_memory_usage("starting PDF embedding storage")
        stored_count = store_pdf_embeddings(chunks)
        
        # Clean up chunks to free memory
        chunk_count = len(chunks)
        del chunks
        import gc
        gc.collect()
        
        processing_time = time.time() - start_time
        
        logger.info(f"SUCCESS: PDF processing completed for {os.path.basename(pdf_path)} in {processing_time:.2f}s")
        log_memory_usage("PDF processing completed")
        
        return PDFIngestResult(
            pdf_id=pdf_id,
            filename=os.path.basename(pdf_path),
            chunks_processed=chunk_count,
            embeddings_stored=stored_count,
            processing_time=processing_time,
            status="success",
            success=True
        )
        
    except Exception as e:
        logger.error(f"PDF ingestion failed: {e}")
        cleanup_memory()
        return PDFIngestResult(
            pdf_id=pdf_id or "unknown",
            filename=os.path.basename(pdf_path) if pdf_path else "unknown",
            chunks_processed=0,
            embeddings_stored=0,
            processing_time=time.time() - start_time,
            status="error",
            success=False,
            error=str(e)
        )


def run_pdf_ingestion_from_content(
    pdf_content: bytes,
    pdf_id: Optional[str] = None,
    pdf_title: Optional[str] = None,
    force_reprocess: bool = False
) -> PDFIngestResult:
    """
    Single source of truth for PDF ingestion pipeline from file content bytes.
    
    This function handles PDF ingestion when you have file content in memory
    (e.g., from FastAPI UploadFile).
    
    Args:
        pdf_content: PDF file content as bytes
        pdf_id: Optional PDF ID (if None, generates from file hash)
        pdf_title: Optional PDF title (if None, uses "uploaded.pdf")
        force_reprocess: Whether to reprocess if PDF already exists
        
    Returns:
        PDFIngestResult with processing details
    """
    import time
    start_time = time.time()
    temp_path = None
    
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before PDF processing")
        cleanup_memory()
    
    try:
        # Generate PDF ID from content if not provided
        if pdf_id is None:
            pdf_id = generate_pdf_id_from_content(pdf_content)
        
        # Use default title if not provided
        if pdf_title is None:
            pdf_title = "uploaded.pdf"
        
        # Write content to temporary file
        temp_dir = os.environ.get("TMPDIR", "/tmp")
        try:
            os.makedirs(temp_dir, exist_ok=True)
        except Exception:
            temp_dir = "/tmp"
        
        temp_path = os.path.join(temp_dir, f"temp_{pdf_id}.pdf")
        with open(temp_path, "wb") as f:
            f.write(pdf_content)
        
        # Use the path-based ingestion function
        result = run_pdf_ingestion_from_path(
            pdf_path=temp_path,
            pdf_id=pdf_id,
            pdf_title=pdf_title,
            force_reprocess=force_reprocess
        )
        
        return result
        
    except Exception as e:
        logger.error(f"PDF ingestion from content failed: {e}")
        cleanup_memory()
        return PDFIngestResult(
            pdf_id=pdf_id or "unknown",
            filename=pdf_title or "unknown",
            chunks_processed=0,
            embeddings_stored=0,
            processing_time=time.time() - start_time,
            status="error",
            success=False,
            error=str(e)
        )
    finally:
        # Clean up temporary file
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.warning(f"Failed to remove temp file {temp_path}: {e}")


# Alias for backward compatibility
run_pdf_ingestion = run_pdf_ingestion_from_path

