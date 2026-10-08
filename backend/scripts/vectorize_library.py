import asyncio
import os
import sys
import structlog
from sqlalchemy import select

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import AsyncSessionLocal
from app.models.clause import StandardClause
from app.services.embedder import generate_embedding

logger = structlog.get_logger(__name__)

# Semaphore to control concurrency against Gemini rate limits
CONCURRENCY_LIMIT = 5
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

async def process_clause(clause, session):
    """Processes and embeds a single clause under concurrency control."""
    async with semaphore:
        try:
            vector = await generate_embedding(clause.standard_text, clause.category)
            clause.embedding = vector
            logger.info("clause_embedded", id=clause.id, title=clause.title)
        except Exception as e:
            logger.error("clause_embedding_failed", id=clause.id, error=str(e))
            raise

async def backfill_standard_clause_vectors():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(StandardClause).where(StandardClause.embedding.is_(None))
        )
        clauses = result.scalars().all()

        if not clauses:
            logger.info("no_clauses_require_vectorization")
            return

        logger.info("starting_vectorization", total_clauses=len(clauses))

        # Run tasks concurrently in batches to avoid network bottlenecks
        batch_size = 20
        for i in range(0, len(clauses), batch_size):
            batch = clauses[i:i + batch_size]
            await asyncio.gather(*(process_clause(clause, session) for clause in batch))
            # Commit intermediate progress so a failure doesn't lose all completed work
            await session.commit()
            logger.info("batch_committed", progress=f"{min(i + batch_size, len(clauses))}/{len(clauses)}")

        logger.info("vectorization_complete")

if __name__ == "__main__":
    asyncio.run(backfill_standard_clause_vectors())