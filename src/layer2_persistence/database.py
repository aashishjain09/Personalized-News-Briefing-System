"""Layer 2: Persistence - Database connection and session management."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
from typing import Generator

from src.layer1_settings import settings, get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """Manages database connections and sessions."""
    
    def __init__(self):
        # Create engine based on config
        if settings.database.type == "postgresql":
            self.engine = create_engine(
                settings.database.url,
                echo=settings.database.echo,
                pool_pre_ping=True,  # Verify connections before using
                pool_recycle=3600,   # Recycle connections every hour
            )
        else:
            raise ValueError(f"Unsupported database type: {settings.database.type}")
        
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        # Log SQL if debug mode
        if settings.app.debug:
            @event.listens_for(self.engine, "before_cursor_execute")
            def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                logger.debug(f"SQL: {statement[:100]}...")
    
    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()
    
    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Context manager for database sessions."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {str(e)}")
            raise
        finally:
            session.close()
    
    def create_tables(self):
        """Create all tables (idempotent)."""
        from src.layer2_persistence.models import Base
        Base.metadata.create_all(self.engine)
        logger.info("Database tables created/verified")
    
    def drop_tables(self):
        """Drop all tables (development only)."""
        from src.layer2_persistence.models import Base
        Base.metadata.drop_all(self.engine)
        logger.warning("All database tables dropped")
    
    def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            with self.engine.connect() as connection:
                connection.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return False


# Global database manager instance
db_manager = DatabaseManager()


def get_db_session() -> Session:
    """Dependency for FastAPI to get database session."""
    return db_manager.get_session()
