from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.utils.file_validation import validate_and_hash_pdf
from app.services.pdf_parser import parse_document
from app.services.llm_extractor import extract_structured_data # <-- NEW IMPORT
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form(default="contract") 
):
    logger.info("document_upload_initiated", filename=file.filename, type=document_type)
    
    try:
        file_hash = await validate_and_hash_pdf(file)

        await file.seek(0)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid PDF file.")
        
    file_bytes = await file.read()
    
    try:
        is_invoice = (document_type.lower() == "invoice")
        
        # PHASE 1: Raw Ingestion (Module 1)
        extracted_data = await parse_document(file_bytes, file.filename, is_invoice)
        
        # PHASE 2: Structured AI Extraction (Module 2)
        structured_intelligence = await extract_structured_data(extracted_data, document_type)
        
        return {
            "data": {
                "file_metadata": {
                    "filename": file.filename,
                    "pages": extracted_data.total_pages,
                    "is_scanned": extracted_data.needs_ocr_fallback
                },
                # Dump the Pydantic model to a JSON dictionary
                "extracted_intelligence": structured_intelligence.model_dump() 
            },
            "meta": {
                "file_hash": file_hash,
                "status": "analysis_complete"
            },
            "error": None
        }
        
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        logger.error("pipeline_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to process document.")