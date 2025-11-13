"""Database connection pooling with asyncpg.

Provides async connection pool management with configurable retry logic and proper resource cleanup.

Retry behavior is controlled by settings.ENABLE_RETRIES:
- False (default): Fail-fast mode for POC/development - immediate failure on connection errors
- True: Production mode - automatic retries (3 attempts, exponential backoff: 2s, 4s, 8s)
"""

import logging
from typing import Any, List, Optional

import asyncpg
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.config import settings

logger = logging.getLogger(__name__)


def conditional_retry(func):
    """Apply retry decorator only if settings.ENABLE_RETRIES is True.

    This allows POC/development mode to fail fast for immediate feedback,
    while production can enable retries for transient connection failures.

    Args:
        func: Async function to conditionally wrap with retry logic

    Returns:
        Either the original function (no retries) or retry-wrapped function
    """
    if settings.ENABLE_RETRIES:
        return retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((
                asyncpg.PostgresConnectionError,
                asyncpg.InterfaceError,
                asyncpg.TooManyConnectionsError,
            )),
            reraise=True,
        )(func)
    return func


# Vector type codec for pgvector
async def _setup_vector_codec(conn: asyncpg.Connection) -> None:
    """Register pgvector codec for converting Python lists to vector type.

    This function is called for each new connection in the pool to register
    a custom codec that converts Python lists to PostgreSQL vector type.

    Args:
        conn: asyncpg connection instance
    """
    await conn.set_type_codec(
        'vector',
        encoder=lambda v: str(v),  # Convert list to '[1.0, 2.0, ...]' string
        decoder=lambda v: [float(x) for x in v.strip('[]').split(',')],  # Parse back to list
        schema='public',
        format='text'
    )


class DatabasePool:
    """Async database connection pool manager with configurable retry logic.

    Provides connection pooling, query execution with optional retries,
    and proper resource cleanup via context manager support.

    Retry behavior is controlled by settings.ENABLE_RETRIES:
    - False (default): Fail-fast mode for POC/development
    - True: Automatic retries (3 attempts, exponential backoff)

    Attributes:
        pool: asyncpg connection pool instance
        min_size: Minimum number of connections in pool
        max_size: Maximum number of connections in pool
    """

    def __init__(self, min_size: int = 5, max_size: int = 20):
        """Initialize database pool configuration.

        Args:
            min_size: Minimum number of connections to maintain (default: 5)
            max_size: Maximum number of connections allowed (default: 20)
        """
        self.pool: Optional[asyncpg.Pool] = None
        self.min_size = min_size
        self.max_size = max_size
        self._connection_params = self._load_connection_params()

        # Log retry configuration
        if settings.ENABLE_RETRIES:
            logger.info("Database retries enabled (3 attempts, exponential backoff)")
        else:
            logger.info("Database retries disabled (fail-fast mode for POC)")

    def _load_connection_params(self) -> dict[str, Any]:
        """Load database connection parameters from settings object.

        Returns:
            Dictionary of connection parameters for asyncpg.create_pool()
        """
        return {"dsn": settings.database_url}

    async def initialize(self) -> None:
        """Create and initialize the connection pool.

        Establishes connection pool with configured min/max sizes.
        Idempotent - safe to call multiple times.

        Raises:
            asyncpg.PostgresError: If connection fails
            ValueError: If connection parameters are invalid
        """
        if self.pool is not None:
            logger.warning("Connection pool already initialized")
            return

        try:
            logger.info(
                f"Initializing connection pool "
                f"(min_size={self.min_size}, max_size={self.max_size})"
            )

            self.pool = await asyncpg.create_pool(
                **self._connection_params,
                min_size=self.min_size,
                max_size=self.max_size,
                command_timeout=60,  # 60s timeout for queries
                init=_setup_vector_codec,  # Register vector codec on each connection
            )

            # Test connection with a simple query
            async with self.pool.acquire() as conn:
                version = await conn.fetchval("SELECT version()")
                logger.info(f"Database connection established: {version}")

        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise

    async def close(self) -> None:
        """Close the connection pool and cleanup resources.

        Gracefully closes all connections in the pool.
        Idempotent - safe to call multiple times.
        """
        if self.pool is None:
            logger.warning("Connection pool not initialized")
            return

        try:
            logger.info("Closing connection pool")
            await self.pool.close()
            self.pool = None
            logger.info("Connection pool closed successfully")
        except Exception as e:
            logger.error(f"Error closing connection pool: {e}")
            raise

    @conditional_retry
    async def execute(
        self,
        query: str,
        *args: Any,
        timeout: Optional[float] = None,
    ) -> str:
        """Execute a query with configurable retry logic.

        Executes INSERT, UPDATE, DELETE, or DDL queries. Connection failure handling
        depends on settings.ENABLE_RETRIES configuration.

        Args:
            query: SQL query to execute
            *args: Query parameters (positional)
            timeout: Optional query timeout in seconds

        Returns:
            Query status string (e.g., "INSERT 0 1", "UPDATE 5")

        Raises:
            ValueError: If pool is not initialized
            asyncpg.PostgresError: If query fails (immediately or after retries)

        Note:
            Retries are configurable via settings.ENABLE_RETRIES.
            For POC/development, retries are disabled for fast failure.

        Example:
            await pool.execute(
                "INSERT INTO documents (id, text) VALUES ($1, $2)",
                "doc1", "Hello world"
            )
        """
        if self.pool is None:
            raise ValueError("Connection pool not initialized. Call initialize() first.")

        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(query, *args, timeout=timeout)
                logger.debug(f"Query executed successfully: {result}")
                return result
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            logger.debug(f"Failed query: {query}")
            raise

    @conditional_retry
    async def executemany(
        self,
        query: str,
        args: List[tuple],
        timeout: Optional[float] = None,
    ) -> None:
        """Execute a query multiple times with different parameters (bulk insert).

        Executes the same query with multiple sets of parameters efficiently.
        Useful for bulk INSERT operations. Connection failure handling depends
        on settings.ENABLE_RETRIES configuration.

        Args:
            query: SQL query to execute (typically INSERT)
            args: List of tuples, each containing parameters for one execution
            timeout: Optional query timeout in seconds

        Returns:
            None (asyncpg executemany returns None)

        Raises:
            ValueError: If pool is not initialized
            asyncpg.PostgresError: If query fails (immediately or after retries)

        Note:
            Retries are configurable via settings.ENABLE_RETRIES.
            For POC/development, retries are disabled for fast failure.
            asyncpg executemany does not return status for individual operations.

        Example:
            records = [
                ("doc1", "Hello world"),
                ("doc2", "Another doc"),
            ]
            await pool.executemany(
                "INSERT INTO documents (id, text) VALUES ($1, $2)",
                records
            )
        """
        if self.pool is None:
            raise ValueError("Connection pool not initialized. Call initialize() first.")

        try:
            async with self.pool.acquire() as conn:
                await conn.executemany(query, args, timeout=timeout)
                logger.debug(f"Query executemany completed: {len(args)} operations")
        except Exception as e:
            logger.error(f"Query executemany failed: {e}")
            logger.debug(f"Failed query: {query}")
            raise

    @conditional_retry
    async def fetch(
        self,
        query: str,
        *args: Any,
        timeout: Optional[float] = None,
    ) -> List[asyncpg.Record]:
        """Fetch query results with configurable retry logic.

        Executes SELECT queries and returns all matching rows. Connection failure
        handling depends on settings.ENABLE_RETRIES configuration.

        Args:
            query: SQL SELECT query
            *args: Query parameters (positional)
            timeout: Optional query timeout in seconds

        Returns:
            List of asyncpg.Record objects (dict-like access to columns)

        Raises:
            ValueError: If pool is not initialized
            asyncpg.PostgresError: If query fails (immediately or after retries)

        Note:
            Retries are configurable via settings.ENABLE_RETRIES.
            For POC/development, retries are disabled for fast failure.

        Example:
            results = await pool.fetch(
                "SELECT * FROM documents WHERE id = $1",
                "doc1"
            )
            for row in results:
                print(row["id"], row["text"])
        """
        if self.pool is None:
            raise ValueError("Connection pool not initialized. Call initialize() first.")

        try:
            async with self.pool.acquire() as conn:
                results = await conn.fetch(query, *args, timeout=timeout)
                logger.debug(f"Query fetched {len(results)} rows")
                return results
        except Exception as e:
            logger.error(f"Query fetch failed: {e}")
            logger.debug(f"Failed query: {query}")
            raise

    @conditional_retry
    async def fetchval(
        self,
        query: str,
        *args: Any,
        timeout: Optional[float] = None,
    ) -> Any:
        """Fetch a single value with configurable retry logic.

        Executes SELECT query and returns the first column of the first row.
        Useful for COUNT(), MAX(), etc. Connection failure handling depends
        on settings.ENABLE_RETRIES configuration.

        Args:
            query: SQL SELECT query
            *args: Query parameters (positional)
            timeout: Optional query timeout in seconds

        Returns:
            Single value from first column of first row, or None if no rows

        Raises:
            ValueError: If pool is not initialized
            asyncpg.PostgresError: If query fails (immediately or after retries)

        Note:
            Retries are configurable via settings.ENABLE_RETRIES.
            For POC/development, retries are disabled for fast failure.

        Example:
            count = await pool.fetchval("SELECT COUNT(*) FROM documents")
        """
        if self.pool is None:
            raise ValueError("Connection pool not initialized. Call initialize() first.")

        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval(query, *args, timeout=timeout)
                logger.debug(f"Query fetchval returned: {result}")
                return result
        except Exception as e:
            logger.error(f"Query fetchval failed: {e}")
            logger.debug(f"Failed query: {query}")
            raise

    @conditional_retry
    async def fetchrow(
        self,
        query: str,
        *args: Any,
        timeout: Optional[float] = None,
    ) -> Optional[asyncpg.Record]:
        """Fetch a single row with configurable retry logic.

        Executes SELECT query and returns the first row. Connection failure
        handling depends on settings.ENABLE_RETRIES configuration.

        Args:
            query: SQL SELECT query
            *args: Query parameters (positional)
            timeout: Optional query timeout in seconds

        Returns:
            First row as asyncpg.Record, or None if no rows

        Raises:
            ValueError: If pool is not initialized
            asyncpg.PostgresError: If query fails (immediately or after retries)

        Note:
            Retries are configurable via settings.ENABLE_RETRIES.
            For POC/development, retries are disabled for fast failure.

        Example:
            row = await pool.fetchrow("SELECT * FROM documents WHERE id = $1", "doc1")
        """
        if self.pool is None:
            raise ValueError("Connection pool not initialized. Call initialize() first.")

        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchrow(query, *args, timeout=timeout)
                logger.debug(f"Query fetchrow returned: {result}")
                return result
        except Exception as e:
            logger.error(f"Query fetchrow failed: {e}")
            logger.debug(f"Failed query: {query}")
            raise

    async def __aenter__(self) -> "DatabasePool":
        """Context manager entry: initialize pool.

        Example:
            async with DatabasePool() as pool:
                await pool.execute("INSERT INTO ...")
        """
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit: cleanup pool."""
        await self.close()
