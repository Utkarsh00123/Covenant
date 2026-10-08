from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings
import structlog

logger = structlog.get_logger(__name__)

# SQLAlchemy 2.0 Async Engine Configuration
# pool_size and max_overflow prevent the server from opening too many connections to Supabase
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False, # Set to True to see raw SQL in the terminal for debugging
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True # Checks if the connection is alive before using it
)

# AsyncSession factory
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# The base class that all our ORM models will inherit from
Base = declarative_base()

async def get_db():
    """
    Dependency injection function for FastAPI endpoints.
    Yields a database session and safely closes it after the request completes.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error("database_session_error", error=str(e))
            await session.rollback()
            raise
        finally:
            await session.close()