import asyncio
import json
import os
import structlog
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from dotenv import load_dotenv

load_dotenv()
logger = structlog.get_logger(__name__)

# Import our models
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.models.clause import StandardClause
from app.core.config import settings

async def seed_standard_clauses():
    """Reads the JSON ground truth and upserts it into PostgreSQL."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # Load JSON
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, "standard_clauses.json")
    
    with open(json_path, "r") as f:
        clauses_data = json.load(f)
        
    async with AsyncSessionLocal() as session:
        for item in clauses_data:
            # Check if clause category already exists to avoid duplicates
            result = await session.execute(
                select(StandardClause).where(StandardClause.category == item["category"])
            )
            existing_clause = result.scalars().first()
            
            if not existing_clause:
                logger.info("inserting_clause", category=item["category"])
                new_clause = StandardClause(
                    category=item["category"],
                    title=item["title"],
                    standard_text=item["standard_text"],
                    risk_description=item["risk_description"],
                    acceptable_ranges=item["acceptable_ranges"]
                )
                session.add(new_clause)
            else:
                logger.info("clause_already_exists", category=item["category"])
                
        await session.commit()
    await engine.dispose()
    logger.info("seeding_complete")

if __name__ == "__main__":
    asyncio.run(seed_standard_clauses())