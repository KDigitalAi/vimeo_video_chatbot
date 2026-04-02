"""
PDF ingestion API endpoint.
"""
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from app.utils.runtime_helpers import get_logger_safe

logger = get_logger_safe(__name__)

try:
    from app.models.schemas import PDFIngestResponse
except ImportError as e:
    logger.error(f"Failed to import PDFIngestResponse: {e}")
    PDFIngestResponse = None

router = APIRouter(
    tags=["pdf"],
    responses={200: {"description": "Successful response"}},
)


def _pdf_not_implemented_message(action: str) -> str:
    if action == "upload":
        return (
            "PDF upload and ingestion are handled by the Assessment system. "
            "Use that pipeline to add documents; the chatbot reads embeddings from Assessment pdf_embeddings."
        )
    return (
        "PDF deletion is handled by the Assessment system. "
        "The chatbot only reads from Assessment pdf_embeddings."
    )


def _build_pdf_resource(pdf_id: str) -> dict:
    from app.services.pdf.pdf_store import get_pdf_embeddings_count

    embedding_count = get_pdf_embeddings_count(pdf_id)
    exists = embedding_count > 0
    return {
        "pdf_id": pdf_id,
        "exists": exists,
        "embedding_count": embedding_count,
        "status": "processed" if exists else "not_found",
        "resource_type": "pdf_document",
    }


def _unsupported_pdf_operation(action: str):
    """Raise the canonical 501 for Assessment-owned PDF lifecycle operations."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=_pdf_not_implemented_message(action),
    )


@router.post(
    "",
    response_model=PDFIngestResponse,
    summary="Create PDF resource",
    description=(
        "Canonical resource-style endpoint for PDF creation. "
        "This service is read-only for PDF ingestion; requests are rejected because the Assessment system owns upload and processing."
    ),
    include_in_schema=False,
)
async def create_pdf(
    file: UploadFile = File(...),
    force_reprocess: bool = Form(False)
):
    """Canonical PDF creation endpoint retained for contract clarity, but not supported by this read-only service."""
    _unsupported_pdf_operation("upload")

@router.post(
    "/batch",
    summary="Create PDF resources in batch",
    description=(
        "Canonical batch-create endpoint for PDF resources. "
        "This service does not own ingestion and therefore returns 501 Not Implemented."
    ),
    include_in_schema=False,
)
async def create_pdf_batch(
    files: list[UploadFile] = File(...),
    force_reprocess: bool = Form(False)
):
    """Canonical batch PDF creation endpoint kept for compatibility with a resource-oriented contract."""
    _unsupported_pdf_operation("upload")

@router.get(
    "",
    summary="List PDF resources",
    description="List processed PDF presence records from the embedding system.",
)
async def list_pdf_collection():
    """Return the PDF resource collection available in the embedding system."""
    from app.services.pdf.pdf_store import list_pdf_documents
    documents = list_pdf_documents()
    return {
        "total_documents": len(documents),
        "documents": documents
    }

@router.get(
    "/{pdf_id}/status",
    summary="Get PDF resource status",
    description="Return processing/presence status for a PDF resource in the embedding system.",
    include_in_schema=False,
)
async def get_pdf_status(pdf_id: str):
    """Return status information for a processed PDF presence resource."""
    return _build_pdf_resource(pdf_id)

@router.get(
    "/{pdf_id}",
    summary="Get PDF resource",
    description=(
        "Return the PDF presence resource as represented by this service: "
        "whether a PDF exists in the embedding system and how many embeddings are currently present."
    ),
)
async def get_pdf_info(pdf_id: str):
    """Return the PDF presence resource tracked by the embedding system."""
    return _build_pdf_resource(pdf_id)

@router.delete(
    "/{pdf_id}",
    summary="Delete PDF resource",
    description=(
        "Canonical delete endpoint for a PDF resource. "
        "Deletion is not supported in this service because the Assessment system owns PDF lifecycle operations."
    ),
    include_in_schema=False,
)
async def delete_pdf(pdf_id: str):
    """Canonical delete endpoint retained for compatibility, but ownership belongs to the Assessment system."""
    _unsupported_pdf_operation("delete")


# Legacy aliases (same handlers; hidden from OpenAPI)
@router.post(
    "/upload",
    response_model=PDFIngestResponse,
    summary="Legacy alias: create PDF resource",
    description="Deprecated alias for `POST /pdf`. Same 501 behavior as the canonical create endpoint.",
    include_in_schema=False,
)
async def ingest_pdf(
    file: UploadFile = File(...),
    force_reprocess: bool = Form(False)
):
    """Backward-compatible alias for PDF creation."""
    return await create_pdf(file, force_reprocess)


@router.post(
    "/upload/batch",
    summary="Legacy alias: batch create PDF resources",
    description="Deprecated alias for `POST /pdf/batch`.",
)
async def ingest_pdf_batch(
    files: list[UploadFile] = File(...),
    force_reprocess: bool = Form(False)
):
    """Backward-compatible alias for batch PDF creation."""
    return await create_pdf_batch(files, force_reprocess)


@router.get(
    "/list",
    summary="Legacy alias: list PDF resources",
    description="Deprecated alias for `GET /pdf`.",
    include_in_schema=False,
)
async def list_pdf_documents():
    """Backward-compatible alias for PDF collection listing."""
    return await list_pdf_collection()
