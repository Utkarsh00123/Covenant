import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.document import Document
from app.models.clause import ExtractedClause as ExtractedClauseModel
from app.services.scoring_engine import evaluate_clause_risk
from app.utils.file_validation import validate_and_hash_pdf
from app.services.pdf_parser import parse_document
from app.services.llm_extractor import extract_structured_data
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form(default="contract"),
    db: AsyncSession = Depends(get_db)
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
        
        # PHASE 3: Persist Document in Database
        existing_doc_res = await db.execute(select(Document).where(Document.file_hash == file_hash))
        existing_doc = existing_doc_res.scalars().first()
        
        if existing_doc:
            doc = existing_doc
            doc.filename = file.filename
            doc.document_type = document_type
            doc.status = "COMPLETED"
        else:
            doc = Document(
                id=uuid.uuid4(),
                filename=file.filename,
                file_hash=file_hash,
                document_type=document_type,
                status="COMPLETED"
            )
            db.add(doc)
            
        await db.commit()
        await db.refresh(doc)

        # Persist clauses and evaluate risk flags if available
        if hasattr(structured_intelligence, "key_clauses") and structured_intelligence.key_clauses:
            for clause in structured_intelligence.key_clauses:
                try:
                    cat_val = clause.category.value if hasattr(clause.category, "value") else str(clause.category)
                    extracted_orm = ExtractedClauseModel(
                        id=uuid.uuid4(),
                        document_id=doc.id,
                        category=cat_val,
                        raw_text=clause.raw_text,
                        extraction_confidence=str(clause.confidence_score)
                    )
                    db.add(extracted_orm)
                    await db.flush()
                    
                    try:
                        flags = await evaluate_clause_risk(
                            db, 
                            doc.id, 
                            extracted_orm, 
                            structured_intelligence.model_dump()
                        )
                        for flag in flags:
                            db.add(flag)
                    except Exception as flag_err:
                        logger.warning("risk_evaluation_skipped", error=str(flag_err))
                except Exception as clause_err:
                    logger.warning("clause_persistence_skipped", error=str(clause_err))
            
            await db.commit()
        
        return {
            "data": {
                "id": str(doc.id),
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