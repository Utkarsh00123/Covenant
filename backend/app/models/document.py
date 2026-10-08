from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.core.database import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    filename = Column(String, nullable=False)
    file_hash = Column(String, unique=True, index=True, nullable=False)
    document_type = Column(String, default="contract") # 'contract' or 'invoice'
    status = Column(String, default="PENDING") # PENDING, COMPLETED, FAILED
    
    # Audit timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class AuditLog(Base):
    """
    Permanent ledger of human interactions with the AI's findings.
    Fulfills the enterprise requirement for compliance tracking.
    """
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    
    # Link to a specific risk flag if the action is tied to one
    risk_flag_id = Column(UUID(as_uuid=True), ForeignKey("risk_flags.id", ondelete="SET NULL"), nullable=True)
    
    # e.g., 'DOCUMENT_APPROVED', 'FLAG_DISMISSED', 'REDLINE_ACCEPTED'
    action_type = Column(String, nullable=False)
    
    # The human-provided justification for the action
    user_reason = Column(String, nullable=True)
    
    # ID of the user who took the action (placeholder for future auth system)
    user_id = Column(String, default="system_user")
    
    # AI Context Snapshot (Using standard JSON as requested)
    # Stores the exact AI reasoning, score, and model version at the time of review.
    ai_state_snapshot = Column(JSON, nullable=True)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now())