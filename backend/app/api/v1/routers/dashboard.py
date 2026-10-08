import uuid
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List

from app.core.database import get_db
from app.models.document import Document
from app.models.clause import RiskFlag
from app.schemas.responses import DocumentListResponse, DocumentDetailResponse
from app.services.scoring_engine import calculate_document_risk_score

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/dashboard", tags=["Dashboard & Analytics"])

@router.get("/documents", response_model=List[DocumentListResponse])
async def list_documents(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns a paginated list of uploaded documents to populate the Next.js datatable.
    Calculates the top-level risk badge and composite score on the fly.
    """
    logger.info("fetching_document_list", limit=limit, offset=offset)
    
    query = select(Document).order_by(desc(Document.created_at)).limit(limit).offset(offset)
    result = await db.execute(query)
    documents = result.scalars().all()
    
    response_list = []
    for doc in documents:
        # Fetch flags to determine the risk badge
        flag_query = select(RiskFlag).where(RiskFlag.document_id == doc.id)
        flag_result = await db.execute(flag_query)
        flags = flag_result.scalars().all()
        
        risk_data = calculate_document_risk_score(flags)
        
        # Convert ORM model to a Pydantic dict and append calculated composite metrics
        doc_data = DocumentListResponse.model_validate(doc).model_dump()
        doc_data["risk_level"] = risk_data["risk_level"] if flags else "PENDING"
        doc_data["numeric_score"] = risk_data["numeric_score"] if flags else None
        
        response_list.append(doc_data)
        
    return response_list

@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
async def get_document_details(document_id: str, db: AsyncSession = Depends(get_db)):
    """
    Fetches the full analysis for a specific document, powering the split-screen UI.
    """
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document UUID format.")
        
    # Fetch Document
    doc_query = select(Document).where(Document.id == doc_uuid)
    doc_result = await db.execute(doc_query)
    document = doc_result.scalars().first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    # Fetch Flags
    flag_query = select(RiskFlag).where(RiskFlag.document_id == doc_uuid)
    flag_result = await db.execute(flag_query)
    flags = flag_result.scalars().all()
    
    # Calculate Risk Metrics
    risk_data = calculate_document_risk_score(flags)
    
    # Prep the nested document dictionary
    doc_data = DocumentListResponse.model_validate(document).model_dump()
    doc_data["risk_level"] = risk_data["risk_level"] if flags else "PENDING"
    doc_data["numeric_score"] = risk_data["numeric_score"] if flags else None
    
    return {
        "document": doc_data,
        "numeric_score": risk_data["numeric_score"] if flags else None,
        "risk_summary": risk_data["summary"] if flags else None,
        "extracted_intelligence": {}, # Ready for future metadata table joins
        "flags": flags # FastAPI/Pydantic automatically serializes the SQLAlchemy models
    }