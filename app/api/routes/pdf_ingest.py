"""
PDF ingestion API endpoint.
"""
import os
import time
import uuid
import gc
from pathlib import Path
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form, Request
from app.utils.runtime_helpers import get_logger_safe, get_settings_safe, memory_guard

logger = get_logger_safe(__name__)

# Safe imports with error handling for serverless environments
try:
    from app.services.pdf_processor import process_pdf_file, validate_pdf_file, get_pdf_metadata
except ImportError as e:
    logger.error(f"Failed to import pdf_processor functions: {e}")
    process_pdf_file = None
    validate_pdf_file = None
    get_pdf_metadata = None

try:
    from app.services.pdf_store import store_pdf_embeddings, check_duplicate_pdf, delete_pdf_embeddings
except ImportError as e:
    logger.error(f"Failed to import pdf_store functions: {e}")
    store_pdf_embeddings = None
    check_duplicate_pdf = None
    delete_pdf_embeddings = None

try:
    from app.utils.logger import log_memory_usage, cleanup_memory
except ImportError:
    def log_memory_usage(*args, **kwargs): pass
    def cleanup_memory(*args, **kwargs): pass

try:
    from app.models.schemas import PDFIngestResponse
except ImportError as e:
    logger.error(f"Failed to import PDFIngestResponse: {e}")
    PDFIngestResponse = None

settings = get_settings_safe()

try:
    from app.services.pdf_ingestion import run_pdf_ingestion_from_content, generate_pdf_id_from_content
except ImportError as e:
    logger.error(f"Failed to import pdf_ingestion service: {e}")
    run_pdf_ingestion_from_content = None
    generate_pdf_id_from_content = None

_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
_BATCH_CLEANUP_INTERVAL = 3

router = APIRouter()

@router.post("/upload", response_model=PDFIngestResponse)
@router.post("/pdf", response_model=PDFIngestResponse)  # Alias for /upload to match documentation
async def ingest_pdf(
    file: UploadFile = File(...),
    force_reprocess: bool = Form(False)
):
    """
    Ingest PDF file using the shared PDF ingestion service.
    
    Args:
        file: PDF file to upload
        force_reprocess: Whether to reprocess if PDF already exists
        
    Returns:
        PDFIngestResponse with processing results
        
    Raises:
        HTTPException: 501 - PDF upload is handled by the Assessment system.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "PDF upload and ingestion are handled by the Assessment system. "
            "Use that pipeline to add documents; the chatbot reads embeddings from Assessment pdf_embeddings."
        )
    )

@router.post("/upload/batch")
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
                    memory_guard(logger, f"batch processing file {i + 1}")
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

@router.get("/list")
async def list_pdf_documents():
    """
    List all PDF documents that have been processed.
    
    Returns:
        List of PDF document information
    """
    try:
        from app.services.pdf_store import list_pdf_documents
        
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

@router.get("/{pdf_id}/status")
async def get_pdf_status(pdf_id: str):
    """
    Get the processing status of a PDF.
    
    Args:
        pdf_id: Unique identifier for the PDF
        
    Returns:
        PDF status information
    """
    try:
        from app.services.pdf_store import get_pdf_embeddings_count
        
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

@router.get("/{pdf_id}")
async def get_pdf_info(pdf_id: str):
    """
    Information endpoint for PDF deletion.
    Returns usage instructions when accessed via GET.
    
    Returns:
        JSON with usage information and PDF status
    """
    try:
        from app.services.pdf_store import get_pdf_embeddings_count
        
        embedding_count = get_pdf_embeddings_count(pdf_id)
        exists = embedding_count > 0
        
        return {
            "message": "PDF deletion endpoint",
            "description": "To delete a PDF, use DELETE /pdf/{pdf_id}",
            "method": "DELETE",
            "endpoint": f"/pdf/{pdf_id}",
            "parameters": {
                "pdf_id": pdf_id
            },
            "current_status": {
                "pdf_id": pdf_id,
                "exists": exists,
                "embedding_count": embedding_count,
                "status": "processed" if exists else "not_found"
            },
            "note": "This endpoint uses DELETE method. Use GET to view this information and current PDF status."
        }
    except Exception as e:
        return {
            "message": "PDF deletion endpoint",
            "description": "To delete a PDF, use DELETE /pdf/{pdf_id}",
            "method": "DELETE",
            "endpoint": f"/pdf/{pdf_id}",
            "parameters": {
                "pdf_id": pdf_id
            },
            "error": f"Could not retrieve PDF status: {str(e)}",
            "note": "This endpoint uses DELETE method. Use GET to view this information."
        }

@router.delete("/{pdf_id}")
async def delete_pdf(pdf_id: str):
    """
    Deletion is handled by the Assessment system; chatbot does not delete from pdf_embeddings.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "PDF deletion is handled by the Assessment system. "
            "The chatbot only reads from Assessment pdf_embeddings."
        )
    )
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
