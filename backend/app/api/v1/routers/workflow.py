import uuid
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.clause import RiskFlag
from app.models.document import AuditLog, Document

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/workflow", tags=["Workflow & Approvals"])

class OverrideRequest(BaseModel):
    status: str # 'DISMISSED', 'ACCEPTED_REDLINE', 'MANUAL_EDIT'
    reason: str

@router.post("/flags/{flag_id}/override")
async def override_risk_flag(
    flag_id: uuid.UUID, # <-- Upgraded to native UUID
    request: OverrideRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Updates a flag's status and permanently logs the human justification.
    """
    if len(request.reason.strip()) < 5:
        raise HTTPException(status_code=400, detail="A detailed justification reason is required.")

    # 1. Fetch Flag
    query = select(RiskFlag).where(RiskFlag.id == flag_id)
    result = await db.execute(query)
    flag = result.scalars().first()
    
    if not flag:
        raise HTTPException(status_code=404, detail="Risk flag not found.")
        
    # 2. Capture AI State Snapshot for Compliance
    # This freezes exactly what Gemini 3.8 Flash recommended at the time of review
    ai_snapshot = {
        "severity": flag.severity,
        "flag_reason": flag.flag_reason,
        "suggested_redline": flag.suggested_redline,
        "plain_english_explanation": flag.plain_english_explanation,
        "similarity_score": flag.similarity_score,
        "ai_model_version": flag.ai_model_version
    }
        
    # 3. Update Flag State
    flag.status = request.status
    flag.user_override_reason = request.reason
    
    # 4. Write to Immutable Audit Log
    audit_entry = AuditLog(
        document_id=flag.document_id,
        risk_flag_id=flag.id,
        action_type=f"FLAG_{request.status}",
        user_reason=request.reason,
        ai_state_snapshot=ai_snapshot # <-- Injected payload
    )
    db.add(audit_entry)
    
    await db.commit()
    logger.info("flag_overridden", flag_id=str(flag_id), status=request.status)
    
    return {"message": "Flag updated successfully and audit log generated."}


class ApproveRequest(BaseModel):
    reason: str

@router.post("/documents/{document_id}/approve")
async def approve_document(
    document_id: uuid.UUID, # <-- Upgraded to native UUID
    request: ApproveRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Finalizes the contract review process, marking it clear for signature.
    """
    # 1. Verify Document
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    doc = result.scalars().first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    # 2. Ensure no OPEN 'CRITICAL' flags remain
    flag_query = select(RiskFlag).where(
        RiskFlag.document_id == document_id, 
        RiskFlag.status == "OPEN",
        RiskFlag.severity == "CRITICAL"
    )
    flag_result = await db.execute(flag_query)
    critical_flags = flag_result.scalars().all()
    
    if critical_flags:
        raise HTTPException(
            status_code=400, 
            detail="Cannot approve document. Critical risk flags must be resolved or dismissed first."
        )
        
    doc.status = "APPROVED"
    
    # 3. Write to Audit Log
    audit_entry = AuditLog(
        document_id=doc.id,
        action_type="DOCUMENT_APPROVED",
        user_reason=request.reason,
        # ai_state_snapshot is omitted here because approval is at the document level
    )
    db.add(audit_entry)
    
    await db.commit()
    logger.info("document_approved", document_id=str(document_id))
    
    return {"message": "Document approved."}