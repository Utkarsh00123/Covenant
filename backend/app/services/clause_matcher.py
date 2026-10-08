import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.clause import StandardClause
from app.services.embedder import generate_embedding

logger = structlog.get_logger(__name__)
# Minimum cosine similarity threshold to consider a standard baseline topic-relevant
MATCH_SIMILARITY_FLOOR = 0.40 

async def find_semantic_match(db: AsyncSession, extracted_text: str, category: str) -> dict | None:
    logger.info("performing_vector_search", category=category, snippet=extracted_text[:60])
    
    try:
        target_vector = await generate_embedding(extracted_text, category)
    except Exception as e:
        logger.error("embedding_generation_failed", category=category, error=str(e))
        return None
    
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
        logger.info("no_standard_clause_in_category", category=category)
        return None
        
    standard_clause, similarity = match[0], float(match[1])
    sim_score = round(similarity, 4)
    
    logger.info("vector_match_found", 
        category=category, 
        title=standard_clause.title, 
        similarity_score=sim_score
    )
    
    if sim_score < MATCH_SIMILARITY_FLOOR:
        logger.warning("match_below_similarity_floor", category=category, similarity=sim_score)
        return None
        
    return {
        "standard_clause_id": str(standard_clause.id),
        "title": standard_clause.title,
        "standard_text": standard_clause.standard_text,
        "risk_description": standard_clause.risk_description,
        "acceptable_ranges": standard_clause.acceptable_ranges,
        "similarity_score": sim_score
    }