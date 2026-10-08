import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.clause import StandardClause
from app.services.embedder import generate_embedding

logger = structlog.get_logger(__name__)
SIMILARITY_THRESHOLD = 0.78 

async def find_semantic_match(db: AsyncSession, extracted_text: str, category: str) -> dict:
    logger.info("performing_vector_search", category=category)
    
    # Fallback: Uses default RETRIEVAL_DOCUMENT task space from embedder.py
    target_vector = await generate_embedding(extracted_text, category)
    
    query = (
        select(
            StandardClause,
            (1 - StandardClause.embedding.cosine_distance(target_vector)).label("similarity_score")
        )
        .where(StandardClause.category == category)
        .where(StandardClause.is_active == True)
        .order_by(StandardClause.embedding.cosine_distance(target_vector))
        .limit(1)
    )
    
    result = await db.execute(query)
    match = result.first()
    
    if not match:
        return None
        
    standard_clause, similarity = match[0], float(match[1])
    
    return {
        "standard_clause_id": str(standard_clause.id),
        "standard_text": standard_clause.standard_text,
        "risk_description": standard_clause.risk_description,
        "acceptable_ranges": standard_clause.acceptable_ranges,
        "similarity_score": round(similarity, 4),
        "is_deviant": similarity < SIMILARITY_THRESHOLD
    }