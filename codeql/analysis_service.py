"""CodeQL analysis service that orchestrates database building, querying, and graph emission."""
from typing import Dict, Any, Optional, List
from core.config import settings
from core.logging import get_logger
from .source_registry import code_source_registry
from .builder import codeql_database_builder
from .query_executor import codeql_query_executor
from .graph_emitter import graph_emitter

logger = get_logger(__name__)


class CodeQLAnalysisService:
    """Service for orchestrating CodeQL analysis and graph building."""

    def __init__(self):
        """Initialize analysis service."""
        self.builder = codeql_database_builder
        self.query_executor = codeql_query_executor
        self.graph_emitter = graph_emitter

    def is_codeql_enabled(self, business_area: str) -> bool:
        """
        Check if CodeQL is enabled for a business area.

        Args:
            business_area: Business area identifier

        Returns:
            True if CodeQL is enabled
        """
        return code_source_registry.is_codeql_enabled(business_area)

    async def analyze_source(self, source_id: str) -> Dict[str, Any]:
        """
        Analyze a single code source.

        Steps:
        1. Get source from registry
        2. Check if commit changed (if Git-based)
        3. Build CodeQL database (if needed)
        4. Execute queries
        5. Emit results to Neo4j graph

        Args:
            source_id: Source ID from registry

        Returns:
            Analysis results
        """
        source = code_source_registry.get(source_id)
        if not source:
            return {
                "status": "error",
                "error": f"Source not found: {source_id}"
            }

        if not source.enabled:
            return {
                "status": "skipped",
                "reason": "source_disabled"
            }

        business_area = source.business_area
        repo_path = source.path

        # Check if CodeQL is enabled for this business area
        if not self.is_codeql_enabled(business_area):
            return {
                "status": "skipped",
                "reason": "codeql_not_enabled_for_business_area"
            }

        logger.info(
            "Starting CodeQL analysis",
            source_id=source_id,
            business_area=business_area,
            repo_path=repo_path
        )

        results = {
            "source_id": source_id,
            "business_area": business_area,
            "repo_path": repo_path,
            "databases": {},
            "queries": {},
            "graph": {}
        }

        # Build databases for each language
        for language in source.languages:
            try:
                # Build database
                db_path = self.builder.build_database(
                    source_id=source_id,
                    repo_path=repo_path,
                    language=language,
                    source_code_path=repo_path  # For GitLab, this would be cloned path
                )

                if not db_path:
                    logger.warning(
                        "Failed to build database",
                        source_id=source_id,
                        language=language
                    )
                    results["databases"][language] = {"status": "failed"}
                    continue

                results["databases"][language] = {
                    "status": "success",
                    "path": db_path
                }

                # Execute queries
                query_results = self.query_executor.execute_all_queries(
                    database_path=db_path,
                    language=language
                )

                results["queries"][language] = query_results

                # Emit to graph
                graph_stats = self.graph_emitter.emit_from_codeql_results(
                    query_results=query_results,
                    business_area=business_area,
                    repo_path=repo_path,
                    language=language
                )

                results["graph"][language] = graph_stats

            except Exception as e:
                logger.error(
                    "Analysis failed for language",
                    source_id=source_id,
                    language=language,
                    error=str(e)
                )
                results["databases"][language] = {"status": "error", "error": str(e)}

        results["status"] = "success"
        logger.info(
            "CodeQL analysis completed",
            source_id=source_id,
            business_area=business_area
        )

        return results

    async def analyze_business_area(self, business_area: str) -> Dict[str, Any]:
        """
        Analyze all sources for a business area.

        Args:
            business_area: Business area identifier

        Returns:
            Aggregated analysis results
        """
        if not self.is_codeql_enabled(business_area):
            return {
                "status": "skipped",
                "reason": "codeql_not_enabled_for_business_area",
                "business_area": business_area
            }

        sources = code_source_registry.list_sources(
            business_area=business_area,
            enabled_only=True
        )

        if not sources:
            return {
                "status": "skipped",
                "reason": "no_sources_registered",
                "business_area": business_area
            }

        logger.info(
            "Analyzing all sources for business area",
            business_area=business_area,
            source_count=len(sources)
        )

        results = {
            "business_area": business_area,
            "sources": {}
        }

        for source in sources:
            source_result = await self.analyze_source(source.source_id)
            results["sources"][source.source_id] = source_result

        results["status"] = "success"
        return results

    def register_source_from_config(
        self,
        business_area: str,
        codeql_config: Dict[str, Any]
    ) -> List[str]:
        """
        Register sources from SOURCES_CONFIG codeql entry.

        Args:
            business_area: Business area identifier
            codeql_config: Parsed codeql config from SOURCES_CONFIG

        Returns:
            List of registered source IDs
        """
        enabled = codeql_config.get("enabled", True)
        if not enabled:
            logger.info(
                "CodeQL disabled for business area",
                business_area=business_area
            )
            return []

        repos = codeql_config.get("repos", [])
        if not repos:
            logger.warning(
                "No repos specified for CodeQL",
                business_area=business_area
            )
            return []

        source_ids = []
        for repo in repos:
            # Determine languages from repo (could be enhanced)
            # For now, default to python for GitLab repos
            languages = ["python", "java"]  # Default, could be configurable

            source_id = code_source_registry.register(
                business_area=business_area,
                source_type="gitlab",
                path=repo,
                languages=languages,
                name=f"{business_area} - {repo}",
                enabled=True
            )
            source_ids.append(source_id)

        logger.info(
            "Registered sources from config",
            business_area=business_area,
            source_count=len(source_ids)
        )

        return source_ids


# Global analysis service instance
codeql_analysis_service = CodeQLAnalysisService()

