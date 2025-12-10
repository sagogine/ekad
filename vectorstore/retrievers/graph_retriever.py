"""Graph retriever for querying Neo4j code graph."""
from typing import Any, Dict, List, Optional
from core.config import settings
from core.logging import get_logger
from core.graph import neo4j_manager
from .base import RetrievedDocument, RetrievalResult, Retriever

logger = get_logger(__name__)


class GraphRetriever(Retriever):
    """Retriever that queries Neo4j code graph for code relationships and dependencies."""

    name = "graph"

    def __init__(self):
        logger.info("Graph retriever initialized")

    def is_available(self) -> bool:
        """Check if graph retriever is available (Neo4j configured and reachable)."""
        return neo4j_manager.is_available()

    async def retrieve(
        self,
        query: str,
        business_area: str,
        *,
        limit: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> RetrievalResult:
        """
        Retrieve code graph context based on query.

        Args:
            query: Search query (e.g., function name, table name, script path)
            business_area: Business area identifier
            limit: Maximum number of results to return
            filters: Optional filters (e.g., node_type, edge_type)

        Returns:
            RetrievalResult with graph context
        """
        if not self.is_available():
            logger.debug("Graph retriever not available, returning empty results")
            return RetrievalResult(
                documents=[],
                retriever_name=self.name,
                source="code_graph",
                message="Graph retriever not available (Neo4j not configured)",
                error="Neo4j not available"
            )

        try:
            # Extract potential identifiers from query
            # Look for function names, table names, script paths, etc.
            context = self._get_graph_context(query, business_area, limit, filters)
            
            documents = []
            for item in context:
                documents.append(
                    RetrievedDocument(
                        content=item.get("content", ""),
                        title=item.get("title", ""),
                        source="code_graph",
                        document_type="code_graph",
                        url=item.get("url", ""),
                        score=item.get("score", 1.0),
                        metadata=item.get("metadata", {})
                    )
                )

            return RetrievalResult(
                documents=documents,
                retriever_name=self.name,
                source="code_graph",
                message=f"Retrieved {len(documents)} graph relationships"
            )

        except Exception as e:
            logger.error(
                "Graph retrieval failed",
                business_area=business_area,
                query=query,
                error=str(e)
            )
            return RetrievalResult(
                documents=[],
                retriever_name=self.name,
                source="code_graph",
                message="Graph retrieval failed",
                error=str(e)
            )

    def _get_graph_context(
        self,
        query: str,
        business_area: str,
        limit: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get graph context for a query.

        Tries multiple strategies:
        1. Find functions/scripts matching query
        2. Find callers/callees
        3. Find subprocess calls
        4. Find table relationships
        """
        context = []

        # Strategy 1: Find nodes matching query
        matching_nodes = self._find_matching_nodes(query, business_area, limit)
        context.extend(matching_nodes)

        # Strategy 2: Find relationships for matching nodes
        if matching_nodes:
            for node in matching_nodes[:5]:  # Limit to avoid too many queries
                node_id = node.get("metadata", {}).get("node_id")
                if node_id:
                    relationships = self._get_node_relationships(node_id, business_area, limit=3)
                    context.extend(relationships)

        # Deduplicate and limit
        seen = set()
        unique_context = []
        for item in context:
            key = item.get("title", "") + item.get("content", "")
            if key not in seen:
                seen.add(key)
                unique_context.append(item)
                if len(unique_context) >= limit:
                    break

        return unique_context

    def _find_matching_nodes(
        self,
        query: str,
        business_area: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Find nodes matching the query."""
        # Search for functions, scripts, files, modules matching query
        cypher = """
        MATCH (n)
        WHERE n.business_area = $business_area
          AND (
            toLower(n.name) CONTAINS toLower($query)
            OR toLower(n.file_path) CONTAINS toLower($query)
            OR toLower(n.path) CONTAINS toLower($query)
          )
        RETURN n, labels(n) as labels
        LIMIT $limit
        """

        try:
            results = neo4j_manager.execute_query(cypher, {
                "business_area": business_area,
                "query": query,
                "limit": limit
            })

            context = []
            for result in results:
                node = result.get("n", {})
                labels = result.get("labels", [])
                node_type = labels[0] if labels else "Node"

                context.append({
                    "title": f"{node_type}: {node.get('name', node.get('path', 'unknown'))}",
                    "content": self._format_node_info(node, node_type),
                    "source": "code_graph",
                    "url": "",
                    "score": 1.0,
                    "metadata": {
                        "node_id": node.get("id"),
                        "node_type": node_type,
                        "business_area": business_area,
                        "repo": node.get("repo"),
                        "file_path": node.get("file_path"),
                        **{k: v for k, v in node.items() if k not in ["id", "name", "path", "file_path", "repo", "business_area"]}
                    }
                })

            return context

        except Exception as e:
            logger.error("Failed to find matching nodes", error=str(e))
            return []

    def _get_node_relationships(
        self,
        node_id: str,
        business_area: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get relationships for a node (callers, callees, subprocess calls)."""
        cypher = """
        MATCH (source {id: $node_id})-[:CALLS|RUNS_SUBPROCESS|IMPORTS]->(target)
        WHERE target.business_area = $business_area
        RETURN source, target, type(relationships(source)[0]) as edge_type
        LIMIT $limit
        UNION
        MATCH (source)-[:CALLS|RUNS_SUBPROCESS|IMPORTS]->(target {id: $node_id})
        WHERE source.business_area = $business_area
        RETURN source, target, type(relationships(source)[0]) as edge_type
        LIMIT $limit
        """

        try:
            results = neo4j_manager.execute_query(cypher, {
                "node_id": node_id,
                "business_area": business_area,
                "limit": limit
            })

            context = []
            for result in results:
                source = result.get("source", {})
                target = result.get("target", {})
                edge_type = result.get("edge_type", "")

                context.append({
                    "title": f"{edge_type}: {source.get('name', 'unknown')} -> {target.get('name', 'unknown')}",
                    "content": f"{edge_type} relationship: {source.get('name')} connects to {target.get('name')}",
                    "source": "code_graph",
                    "url": "",
                    "score": 0.9,
                    "metadata": {
                        "edge_type": edge_type,
                        "source_id": source.get("id"),
                        "target_id": target.get("id"),
                        "business_area": business_area
                    }
                })

            return context

        except Exception as e:
            logger.error("Failed to get node relationships", error=str(e))
            return []

    def _format_node_info(self, node: Dict[str, Any], node_type: str) -> str:
        """Format node information as text."""
        info_parts = [f"{node_type}: {node.get('name', node.get('path', 'unknown'))}"]
        
        if node.get("file_path"):
            info_parts.append(f"File: {node.get('file_path')}")
        
        if node.get("line_start") and node.get("line_end"):
            info_parts.append(f"Lines: {node.get('line_start')}-{node.get('line_end')}")
        
        if node.get("repo"):
            info_parts.append(f"Repo: {node.get('repo')}")
        
        return "\n".join(info_parts)

    def get_callers(self, function_name: str, business_area: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get functions that call a given function (upstream).

        Args:
            function_name: Function name to find callers for
            business_area: Business area identifier
            limit: Maximum results

        Returns:
            List of caller functions
        """
        if not self.is_available():
            return []

        cypher = """
        MATCH (caller:Function)-[:CALLS]->(callee:Function {name: $function_name})
        WHERE caller.business_area = $business_area AND callee.business_area = $business_area
        RETURN caller
        LIMIT $limit
        """

        try:
            results = neo4j_manager.execute_query(cypher, {
                "function_name": function_name,
                "business_area": business_area,
                "limit": limit
            })
            return [r.get("caller", {}) for r in results]
        except Exception as e:
            logger.error("Failed to get callers", error=str(e))
            return []

    def get_callees(self, function_name: str, business_area: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get functions called by a given function (downstream).

        Args:
            function_name: Function name to find callees for
            business_area: Business area identifier
            limit: Maximum results

        Returns:
            List of callee functions
        """
        if not self.is_available():
            return []

        cypher = """
        MATCH (caller:Function {name: $function_name})-[:CALLS]->(callee:Function)
        WHERE caller.business_area = $business_area AND callee.business_area = $business_area
        RETURN callee
        LIMIT $limit
        """

        try:
            results = neo4j_manager.execute_query(cypher, {
                "function_name": function_name,
                "business_area": business_area,
                "limit": limit
            })
            return [r.get("callee", {}) for r in results]
        except Exception as e:
            logger.error("Failed to get callees", error=str(e))
            return []

    def get_graph_context_for_table(
        self,
        table_name: str,
        business_area: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get code that touches a table (for data flow queries).

        Args:
            table_name: Table name
            business_area: Business area identifier
            limit: Maximum results

        Returns:
            List of code nodes that reference the table
        """
        if not self.is_available():
            return []

        # This would need TOUCHES_TABLE edges (to be added when implementing data flow)
        # For now, return empty
        logger.debug("Table context query not yet implemented (requires data flow edges)")
        return []

    def get_graph_context_for_script(
        self,
        script_path: str,
        business_area: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get code that calls a script (callers and related code).

        Args:
            script_path: Script path
            business_area: Business area identifier
            limit: Maximum results

        Returns:
            List of code nodes that call the script
        """
        if not self.is_available():
            return []

        cypher = """
        MATCH (caller)-[:RUNS_SUBPROCESS]->(script:Script {path: $script_path})
        WHERE caller.business_area = $business_area AND script.business_area = $business_area
        RETURN caller, script
        LIMIT $limit
        """

        try:
            results = neo4j_manager.execute_query(cypher, {
                "script_path": script_path,
                "business_area": business_area,
                "limit": limit
            })
            return [
                {
                    "caller": r.get("caller", {}),
                    "script": r.get("script", {})
                }
                for r in results
            ]
        except Exception as e:
            logger.error("Failed to get script context", error=str(e))
            return []


# Global graph retriever instance
graph_retriever = GraphRetriever()

