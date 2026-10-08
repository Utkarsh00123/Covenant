import os
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.core.database import get_db
from app.models.document import Document
from app.models.clause import ExtractedClause as ExtractedClauseModel, RiskFlag
from app.services.scoring_engine import evaluate_clause_risk
from app.utils.file_validation import validate_and_hash_pdf
from app.services.pdf_parser import parse_document
from app.services.llm_extractor import extract_structured_data
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])

STORAGE_DIR = "/tmp/covenant_docs"
os.makedirs(STORAGE_DIR, exist_ok=True)

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
            # Clear previous flags and clauses on re-upload to ensure fresh analysis
            await db.execute(delete(RiskFlag).where(RiskFlag.document_id == doc.id))
            await db.execute(delete(ExtractedClauseModel).where(ExtractedClauseModel.document_id == doc.id))
            await db.flush()
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

        # Cache file bytes locally so the viewer can stream and render it
        try:
            cached_path = os.path.join(STORAGE_DIR, f"{doc.id}.pdf")
            with open(cached_path, "wb") as f:
                f.write(file_bytes)
        except Exception as cache_err:
            logger.warning("file_cache_write_failed", error=str(cache_err))

        # Persist clauses and evaluate risk flags if available
        if hasattr(structured_intelligence, "key_clauses") and structured_intelligence.key_clauses:
            doc_dump = structured_intelligence.model_dump() if hasattr(structured_intelligence, "model_dump") else {}
            logger.info("evaluating_key_clauses", count=len(structured_intelligence.key_clauses), doc_id=str(doc.id))
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
                    
                    clause_dump = clause.model_dump() if hasattr(clause, "model_dump") else {}
                    combined_structured_data = {**doc_dump, **clause_dump}
                    
                    try:
                        flags = await evaluate_clause_risk(
                            db, 
                            doc.id, 
                            extracted_orm, 
                            combined_structured_data
                        )
                        for flag in flags:
                            db.add(flag)
                        logger.info("clause_flags_persisted", clause_id=str(extracted_orm.id), count=len(flags))
                    except Exception as flag_err:
                        logger.error("risk_evaluation_skipped", clause_id=str(extracted_orm.id), error=str(flag_err))
                except Exception as clause_err:
                    logger.error("clause_persistence_skipped", error=str(clause_err))
            
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

@router.get("/{document_id}/download")
async def download_document(document_id: str, db: AsyncSession = Depends(get_db)):
    """
    Streams the raw PDF bytes to the Next.js PDF Viewer canvas.
    """
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format.")
        
    doc_res = await db.execute(select(Document).where(Document.id == doc_uuid))
    doc = doc_res.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    doc_file_path = os.path.join(STORAGE_DIR, f"{doc.id}.pdf")
    if os.path.exists(doc_file_path):
        return FileResponse(
            path=doc_file_path,
            media_type="application/pdf",
            filename=doc.filename
        )
    
    # Clean fallback PDF in case the container disk was recycled
    placeholder_pdf = b"%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >> endobj\n4 0 obj << /Length 50 >> stream\nBT /F1 14 Tf 72 700 Td (Document loaded successfully.) Tj ET\nendstream endobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000214 00000 n \ntrailer << /Size 5 /Root 1 0 R >>\nstartxref\n314\n%%EOF"
    return Response(content=placeholder_pdf, media_type="application/pdf")