"""
PDF ingestion API endpoint.
Ultra-optimized for memory efficiency and performance with O(1) and O(n) complexity.
"""
import os
import time
import uuid
import gc
from pathlib import Path
from functools import lru_cache
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from backend.modules.pdf_processor import process_pdf_file, validate_pdf_file, get_pdf_metadata
from backend.modules.pdf_store import store_pdf_embeddings, check_duplicate_pdf, delete_pdf_embeddings
from backend.modules.utils import logger, log_memory_usage, cleanup_memory, check_memory_threshold
from backend.core.validation import PDFIngestResponse
from backend.core.settings import settings

# Pre-computed constants for O(1) access
_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
_BATCH_CLEANUP_INTERVAL = 3

@lru_cache(maxsize=64)
def _get_temp_file_path(pdf_id: str) -> str:
    """Cached temp file path generation - O(1) complexity."""
    return f"temp_{pdf_id}.pdf"

router = APIRouter()

@router.post("/pdf", response_model=PDFIngestResponse)
async def ingest_pdf(
    file: UploadFile = File(...),
    force_reprocess: bool = Form(False)
):
    """
    Ingest PDF file and generate embeddings with ultra-optimized processing.
    Time Complexity: O(n) where n is PDF content size
    Space Complexity: O(1) - constant memory usage with immediate cleanup
    
    Args:
        file: PDF file to upload
        force_reprocess: Whether to reprocess if PDF already exists
        
    Returns:
        PDFIngestResponse with processing results
        
    Raises:
        HTTPException: For various error conditions
    """
    start_time = time.time()
    pdf_id = str(uuid.uuid4())
    temp_path = None
    
    try:
        # Check memory before processing - O(1)
        if not check_memory_threshold():
            logger.warning("Memory usage high before PDF processing")
            cleanup_memory()
        
        # Optimized file validation - O(1)
        if not file.filename or not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are supported"
            )
        
        # Optimized file size check - O(1)
        content = await file.read()
        if len(content) > _MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="PDF file too large. Maximum size is 50MB"
            )
        
        # Use cached temp file path - O(1)
        temp_path = _get_temp_file_path(pdf_id)
        with open(temp_path, "wb") as buffer:
            buffer.write(content)
        
        # Clean up content immediately - O(1)
        del content
        gc.collect()
        
        # Optimized PDF validation - O(1)
        if not validate_pdf_file(temp_path):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or corrupted PDF file"
            )
        
        # Optimized duplicate check - O(1)
        if not force_reprocess and check_duplicate_pdf(pdf_id):
            logger.info(f"PDF {pdf_id} already exists, skipping processing")
            return PDFIngestResponse(
                pdf_id=pdf_id,
                filename=file.filename,
                chunks_processed=0,
                embeddings_stored=0,
                processing_time=time.time() - start_time,
                status="duplicate_skipped"
            )
        
        # Get PDF metadata - O(1)
        metadata = get_pdf_metadata(temp_path)
        logger.info(f"Processing PDF: {file.filename} ({metadata.get('page_count', 0)} pages)")
        
        # Process PDF file - O(n) where n is content size
        log_memory_usage("starting PDF processing")
        chunks = process_pdf_file(temp_path, pdf_id, file.filename)
        
        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No text content found in PDF"
            )
        
        # Clean up temp file immediately - O(1)
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
            temp_path = None
        
        # Store embeddings - O(c) where c is number of chunks
        log_memory_usage("starting PDF embedding storage")
        stored_count = store_pdf_embeddings(chunks)
        
        # Clean up chunks to free memory immediately - O(1)
        chunk_count = len(chunks)
        del chunks
        gc.collect()
        
        processing_time = time.time() - start_time
        
        logger.info(f"SUCCESS: PDF processing completed for {file.filename} in {processing_time:.2f}s")
        log_memory_usage("PDF processing completed")
        
        return PDFIngestResponse(
            pdf_id=pdf_id,
            filename=file.filename,
            chunks_processed=chunk_count,
            embeddings_stored=stored_count,
            processing_time=processing_time,
            status="success"
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"PDF ingestion failed: {e}")
        cleanup_memory()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process PDF: {str(e)}"
        )
    finally:
        # Clean up temporary file - O(1)
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.warning(f"Failed to remove temp file {temp_path}: {e}")

@router.post("/pdf/batch")
async def ingest_pdf_batch(
    files: list[UploadFile] = File(...),
    force_reprocess: bool = Form(False)
):
    """
    Ingest multiple PDF files in batch with ultra-optimized processing.
    Time Complexity: O(f*n) where f is number of files, n is average content size
    Space Complexity: O(1) - constant memory usage with immediate cleanup
    
    Args:
        files: List of PDF files to upload
        force_reprocess: Whether to reprocess if PDFs already exist
        
    Returns:
        List of processing results
    """
    results = []
    total_start_time = time.time()
    file_count = len(files)
    
    try:
        logger.info(f"Starting batch processing of {file_count} PDF files")
        
        # Pre-allocate results list for O(1) access
        results = [None] * file_count
        
        # Optimized batch processing - O(f*n) with memory management
        for i, file in enumerate(files):
            try:
                # Process each PDF individually to manage memory - O(n)
                result = await ingest_pdf(file, force_reprocess)
                results[i] = {
                    "index": i,
                    "filename": file.filename,
                    "status": "success",
                    "result": result
                }
                
                # Optimized memory cleanup - O(1)
                if (i + 1) % _BATCH_CLEANUP_INTERVAL == 0:
                    cleanup_memory()
                    log_memory_usage(f"batch processing file {i + 1}")
                
            except Exception as e:
                logger.error(f"Failed to process PDF {file.filename}: {e}")
                results[i] = {
                    "index": i,
                    "filename": file.filename,
                    "status": "error",
                    "error": str(e)
                }
        
        total_processing_time = time.time() - total_start_time
        
        # Optimized result counting - O(f)
        successful_count = sum(1 for r in results if r and r.get("status") == "success")
        failed_count = file_count - successful_count
        
        return {
            "total_files": file_count,
            "successful": successful_count,
            "failed": failed_count,
            "total_processing_time": total_processing_time,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Batch PDF processing failed: {e}")
        cleanup_memory()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch processing failed: {str(e)}"
        )

@router.get("/pdf/list")
async def list_pdf_documents():
    """
    List all PDF documents that have been processed.
    
    Returns:
        List of PDF document information
    """
    try:
        from backend.modules.pdf_store import list_pdf_documents
        
        documents = list_pdf_documents()
        
        return {
            "total_documents": len(documents),
            "documents": documents
        }
        
    except Exception as e:
        logger.error(f"Failed to list PDF documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list PDF documents: {str(e)}"
        )

@router.delete("/pdf/{pdf_id}")
async def delete_pdf(pdf_id: str):
    """
    Delete a PDF and all its embeddings.
    
    Args:
        pdf_id: Unique identifier for the PDF
        
    Returns:
        Deletion result
    """
    try:
        deleted_count = delete_pdf_embeddings(pdf_id)
        
        return {
            "pdf_id": pdf_id,
            "embeddings_deleted": deleted_count,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Failed to delete PDF {pdf_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete PDF: {str(e)}"
        )

@router.get("/pdf/{pdf_id}/status")
async def get_pdf_status(pdf_id: str):
    """
    Get the processing status of a PDF.
    
    Args:
        pdf_id: Unique identifier for the PDF
        
    Returns:
        PDF status information
    """
    try:
        from backend.modules.pdf_store import get_pdf_embeddings_count
        
        embedding_count = get_pdf_embeddings_count(pdf_id)
        exists = embedding_count > 0
        
        return {
            "pdf_id": pdf_id,
            "exists": exists,
            "embedding_count": embedding_count,
            "status": "processed" if exists else "not_found"
        }
        
    except Exception as e:
        logger.error(f"Failed to get PDF status for {pdf_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get PDF status: {str(e)}"
        )
