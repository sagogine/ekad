"""Neo4j graph database manager for code lineage."""
from typing import Optional, Dict, Any, List
from neo4j import GraphDatabase, Driver
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class Neo4jManager:
    """Manager for Neo4j graph database with optional availability."""

    def __init__(self):
        """Initialize Neo4j manager."""
        self._driver: Optional[Driver] = None
        self._available: Optional[bool] = None
        self._initialize()

    def _initialize(self) -> None:
        """Initialize Neo4j connection if configured."""
        neo4j_url = settings.neo4j_url
        neo4j_user = settings.neo4j_user
        neo4j_password = settings.get_secret_value(settings.neo4j_password, field_name="neo4j_password")

        if not all([neo4j_url, neo4j_user, neo4j_password]):
            logger.info(
                "Neo4j not configured (missing URL, user, or password). "
                "Code graph features will be disabled."
            )
            self._available = False
            return

        try:
            self._driver = GraphDatabase.driver(
                neo4j_url,
                auth=(neo4j_user, neo4j_password)
            )
            # Test connection
            with self._driver.session() as session:
                session.run("RETURN 1")
            self._available = True
            logger.info("Neo4j connection established", url=neo4j_url)
        except Exception as e:
            logger.warning(
                "Neo4j connection failed, code graph features will be disabled",
                error=str(e),
                url=neo4j_url
            )
            self._available = False
            self._driver = None

    def is_available(self) -> bool:
        """
        Check if Neo4j is available and configured.

        Returns:
            True if Neo4j is available, False otherwise
        """
        if self._available is None:
            # Re-check availability
            self._initialize()
        return self._available is True

    def get_driver(self) -> Optional[Driver]:
        """
        Get Neo4j driver if available.

        Returns:
            Neo4j driver or None if not available
        """
        if not self.is_available():
            return None
        return self._driver

    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records as dictionaries

        Raises:
            ValueError: If Neo4j is not available
        """
        if not self.is_available():
            raise ValueError("Neo4j is not available or not configured")

        if not self._driver:
            raise ValueError("Neo4j driver not initialized")

        try:
            with self._driver.session() as session:
                result = session.run(query, parameters or {})
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(
                "Neo4j query execution failed",
                query=query[:100],
                error=str(e)
            )
            raise

    def initialize_schema(self) -> None:
        """
        Initialize Neo4j schema with constraints and indexes.

        Creates:
        - Constraints on node labels (Function, Class, File, etc.)
        - Indexes on common properties (business_area, repo, etc.)
        """
        if not self.is_available():
            logger.warning("Cannot initialize schema: Neo4j not available")
            return

        schema_queries = [
            # Constraints for unique node identification
            "CREATE CONSTRAINT function_id IF NOT EXISTS FOR (f:Function) REQUIRE f.id IS UNIQUE",
            "CREATE CONSTRAINT class_id IF NOT EXISTS FOR (c:Class) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT file_id IF NOT EXISTS FOR (f:File) REQUIRE f.id IS UNIQUE",
            "CREATE CONSTRAINT script_id IF NOT EXISTS FOR (s:Script) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT table_id IF NOT EXISTS FOR (t:Table) REQUIRE t.id IS UNIQUE",
            "CREATE CONSTRAINT pipeline_id IF NOT EXISTS FOR (p:Pipeline) REQUIRE p.id IS UNIQUE",
            
            # Indexes for common queries (Neo4j 5 syntax - label-specific only)
            "CREATE RANGE INDEX file_path_index IF NOT EXISTS FOR (f:File) ON (f.file_path)",
            # Note: Cannot create indexes on all nodes without labels in Neo4j 5
            # We'll use label-specific indexes in queries instead
        ]

        try:
            with self._driver.session() as session:
                for query in schema_queries:
                    try:
                        session.run(query)
                        logger.debug("Executed schema query", query=query[:50])
                    except Exception as e:
                        # Ignore errors for existing constraints/indexes
                        if "already exists" not in str(e).lower():
                            logger.warning("Schema query failed", query=query[:50], error=str(e))
            
            logger.info("Neo4j schema initialized")
        except Exception as e:
            logger.error("Failed to initialize Neo4j schema", error=str(e))
            raise

    def close(self) -> None:
        """Close Neo4j driver connection."""
        if self._driver:
            try:
                self._driver.close()
                logger.info("Neo4j connection closed")
            except Exception as e:
                logger.warning("Error closing Neo4j connection", error=str(e))
            finally:
                self._driver = None
                self._available = False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Global Neo4j manager instance
neo4j_manager = Neo4jManager()

