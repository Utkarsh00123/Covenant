from sqlalchemy import Column, String, Integer,Boolean, DateTime, ForeignKey, JSON, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import uuid
from app.core.database import Base

class StandardClause(Base):
    """
    The version-controlled library of expected standard terms.
    """
    __tablename__ = "standard_clauses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(String, index=True, nullable=False) # e.g., LIABILITY_CAP
    title = Column(String, nullable=False)
    
    # The ideal, baseline text to compare against
    standard_text = Column(String, nullable=False)
    
    # Plain English explanation of why deviating is risky
    risk_description = Column(String, nullable=False)
    
    # JSON containing mathematical thresholds (e.g., {"max_renewal_months": 12})
    acceptable_ranges = Column(JSON, nullable=True) 
    
    # 768-dimensional vector for Google's text-embedding-004
    embedding = Column(Vector(768)) 
    
    # Version control
    version = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ExtractedClause(Base):
    """
    Clauses parsed out of uploaded documents.
    """
    __tablename__ = "extracted_clauses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    category = Column(String, index=True, nullable=False)
    
    # Verbatim text from the PDF
    raw_text = Column(String, nullable=False)
    
    # Confidence score from the LLM extraction step
    extraction_confidence = Column(String, nullable=True)
    
    # The vector representation of the extracted text (768 dimensions for Gemini)
    embedding = Column(Vector(768))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RiskFlag(Base):
    """
    Represents a specific risk found in an uploaded document.
    """
    __tablename__ = "risk_flags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    
    # Evidence Binding
    extracted_clause_id = Column(UUID(as_uuid=True), ForeignKey("extracted_clauses.id", ondelete="CASCADE"), nullable=False)
    standard_clause_id = Column(UUID(as_uuid=True), ForeignKey("standard_clauses.id", ondelete="SET NULL"), nullable=True)
    
    flag_type = Column(String, nullable=False) 
    severity = Column(String, nullable=False)  
    flag_reason = Column(String, nullable=False)
    
    # Audit Fields
    similarity_score = Column(Float, nullable=True) 
    ai_model_version = Column(String, default="gemini-3.1-flash-lite", nullable=True) 
    
    evidence_text = Column(String, nullable=False)
    baseline_text = Column(String, nullable=True)
    
    # --- NEW REDLINE FIELDS ---
    suggested_redline = Column(String, nullable=True) 
    plain_english_explanation = Column(String, nullable=True)
    
    # Reverted to standard JSON as requested
    redline_diff = Column(JSON, nullable=True) 
    
    status = Column(String, default="OPEN") 
    user_override_reason = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())