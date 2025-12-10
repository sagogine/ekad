"""CodeQL query executor for running queries and extracting results."""
from pathlib import Path
from typing import List, Dict, Any, Optional
from core.logging import get_logger
from .cli import get_codeql_cli

logger = get_logger(__name__)


class CodeQLQueryExecutor:
    """Executes CodeQL queries and extracts graph relationships."""

    def __init__(self, queries_dir: Optional[str] = None):
        """
        Initialize query executor.

        Args:
            queries_dir: Directory containing .ql query files (defaults to codeql/queries/)
        """
        if queries_dir:
            self.queries_dir = Path(queries_dir)
        else:
            # Default to codeql/queries/ relative to this file
            self.queries_dir = Path(__file__).parent.parent / "codeql" / "queries"
        
        self.cli = get_codeql_cli()
        logger.info("CodeQL query executor initialized", queries_dir=str(self.queries_dir))

    def execute_query(
        self,
        database_path: str,
        query_file: str
    ) -> List[Dict[str, Any]]:
        """
        Execute a CodeQL query and return results.

        Args:
            database_path: Path to CodeQL database
            query_file: Name of query file (e.g., "call_graph.ql") or full path

        Returns:
            List of query results as dictionaries
        """
        if not self.cli:
            logger.error("CodeQL CLI not available")
            return []

        # Resolve query file path
        if Path(query_file).is_absolute():
            query_path = Path(query_file)
        else:
            query_path = self.queries_dir / query_file

        if not query_path.exists():
            logger.error("Query file not found", query_file=str(query_path))
            return []

        try:
            results = self.cli.query_run(
                database_path=database_path,
                query_file=str(query_path),
                format="json"
            )

            # Parse results
            if isinstance(results, dict) and "results" in results:
                return results["results"]
            elif isinstance(results, list):
                return results
            else:
                logger.warning("Unexpected query result format", results_type=type(results))
                return []

        except Exception as e:
            logger.error(
                "Failed to execute CodeQL query",
                query_file=str(query_path),
                error=str(e)
            )
            return []

    def execute_all_queries(
        self,
        database_path: str,
        language: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Execute all relevant queries for a language.

        Args:
            database_path: Path to CodeQL database
            language: Language (python, java, etc.)

        Returns:
            Dictionary mapping query names to results
        """
        all_results = {}

        # Map languages to query files
        query_map = {
            "python": ["call_graph.ql", "subprocess_calls.ql", "imports.ql"],
            "java": ["call_graph.ql"],  # TODO: Add Java-specific queries
        }

        queries = query_map.get(language, [])
        if not queries:
            logger.warning("No queries defined for language", language=language)
            return all_results

        for query_file in queries:
            query_name = Path(query_file).stem
            try:
                results = self.execute_query(database_path, query_file)
                all_results[query_name] = results
                logger.info(
                    "Executed query",
                    query=query_name,
                    results_count=len(results)
                )
            except Exception as e:
                logger.error(
                    "Failed to execute query",
                    query=query_name,
                    error=str(e)
                )
                all_results[query_name] = []

        return all_results

    def list_available_queries(self) -> List[str]:
        """
        List available query files.

        Returns:
            List of query file names
        """
        if not self.queries_dir.exists():
            return []

        queries = [
            q.name for q in self.queries_dir.glob("*.ql")
        ]
        return sorted(queries)


# Global query executor instance
codeql_query_executor = CodeQLQueryExecutor()

