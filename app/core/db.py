from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


Base = declarative_base()


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

logger.info("Async SQLAlchemy engine created (echo=%s)", settings.DEBUG)


async_session_factory = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    """
    Provide an async SQLAlchemy session for each request.
    """
    logger.debug("Opening async DB session")
    async with async_session_factory() as session:
        try:
            logger.debug("Providing DB session to caller")
            yield session
        finally:
            logger.debug("Async DB session closed")
