"""Graph emitter that converts CodeQL results to Neo4j graph."""
from typing import Dict, List, Any, Optional
from core.graph import neo4j_manager
from core.logging import get_logger

logger = get_logger(__name__)


class GraphEmitter:
    """Emits CodeQL analysis results as Neo4j graph nodes and edges."""

    def __init__(self):
        """Initialize graph emitter."""
        if not neo4j_manager.is_available():
            logger.warning("Neo4j not available, graph emitter will not work")

    def emit_from_codeql_results(
        self,
        query_results: Dict[str, List[Dict[str, Any]]],
        business_area: str,
        repo_path: str,
        language: str
    ) -> Dict[str, int]:
        """
        Emit graph from CodeQL query results.

        Args:
            query_results: Dictionary mapping query names to results
            business_area: Business area identifier
            repo_path: Repository path
            language: Language

        Returns:
            Dictionary with counts of nodes and edges created
        """
        if not neo4j_manager.is_available():
            logger.warning("Neo4j not available, skipping graph emission")
            return {"nodes": 0, "edges": 0}

        # Delete existing graph for this repo (full rebuild)
        self._delete_repo_graph(business_area, repo_path)

        node_count = 0
        edge_count = 0

        # Process each query's results
        for query_name, results in query_results.items():
            if query_name == "call_graph":
                nodes, edges = self._emit_call_graph(results, business_area, repo_path)
                node_count += nodes
                edge_count += edges
            elif query_name == "subprocess_calls":
                nodes, edges = self._emit_subprocess_calls(results, business_area, repo_path)
                node_count += nodes
                edge_count += edges
            elif query_name == "imports":
                nodes, edges = self._emit_imports(results, business_area, repo_path)
                node_count += nodes
                edge_count += edges

        logger.info(
            "Emitted graph from CodeQL results",
            business_area=business_area,
            repo=repo_path,
            nodes=node_count,
            edges=edge_count
        )

        return {"nodes": node_count, "edges": edge_count}

    def _delete_repo_graph(self, business_area: str, repo_path: str) -> None:
        """Delete all nodes and edges for a repository."""
        query = """
        MATCH (n)
        WHERE n.business_area = $business_area AND n.repo = $repo_path
        DETACH DELETE n
        """
        try:
            neo4j_manager.execute_query(query, {
                "business_area": business_area,
                "repo_path": repo_path
            })
            logger.info(
                "Deleted existing graph for repo",
                business_area=business_area,
                repo=repo_path
            )
        except Exception as e:
            logger.error(
                "Failed to delete repo graph",
                business_area=business_area,
                repo=repo_path,
                error=str(e)
            )

    def _emit_call_graph(
        self,
        results: List[Dict[str, Any]],
        business_area: str,
        repo_path: str
    ) -> tuple[int, int]:
        """Emit function call graph edges."""
        if not results:
            return 0, 0

        nodes_created = set()
        edges_created = 0

        for result in results:
            # Extract caller and callee from result
            # CodeQL JSON format: {"#1": {"label": "caller"}, "#2": {"label": "callee"}}
            caller = self._extract_node_from_result(result, "#1")
            callee = self._extract_node_from_result(result, "#2")

            if not caller or not callee:
                continue

            # Create nodes
            caller_id = self._create_function_node(caller, business_area, repo_path)
            callee_id = self._create_function_node(callee, business_area, repo_path)

            if caller_id not in nodes_created:
                nodes_created.add(caller_id)
            if callee_id not in nodes_created:
                nodes_created.add(callee_id)

            # Create edge
            self._create_edge(caller_id, "CALLS", callee_id, business_area, repo_path)
            edges_created += 1

        return len(nodes_created), edges_created

    def _emit_subprocess_calls(
        self,
        results: List[Dict[str, Any]],
        business_area: str,
        repo_path: str
    ) -> tuple[int, int]:
        """Emit subprocess call edges."""
        if not results:
            return 0, 0

        nodes_created = set()
        edges_created = 0

        for result in results:
            func = self._extract_node_from_result(result, "#1")
            script_path = self._extract_node_from_result(result, "#2")

            if not func or not script_path:
                continue

            # Create function node
            func_id = self._create_function_node(func, business_area, repo_path)
            if func_id not in nodes_created:
                nodes_created.add(func_id)

            # Create script node
            script_id = self._create_script_node(script_path, business_area, repo_path)
            if script_id not in nodes_created:
                nodes_created.add(script_id)

            # Create edge
            self._create_edge(func_id, "RUNS_SUBPROCESS", script_id, business_area, repo_path)
            edges_created += 1

        return len(nodes_created), edges_created

    def _emit_imports(
        self,
        results: List[Dict[str, Any]],
        business_area: str,
        repo_path: str
    ) -> tuple[int, int]:
        """Emit import relationships."""
        if not results:
            return 0, 0

        nodes_created = set()
        edges_created = 0

        for result in results:
            file_node = self._extract_node_from_result(result, "#1")
            module_name = self._extract_node_from_result(result, "#2")

            if not file_node or not module_name:
                continue

            # Create file node
            file_id = self._create_file_node(file_node, business_area, repo_path)
            if file_id not in nodes_created:
                nodes_created.add(file_id)

            # Create module node
            module_id = self._create_module_node(module_name, business_area, repo_path)
            if module_id not in nodes_created:
                nodes_created.add(module_id)

            # Create edge
            self._create_edge(file_id, "IMPORTS", module_id, business_area, repo_path)
            edges_created += 1

        return len(nodes_created), edges_created

    def _extract_node_from_result(self, result: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
        """Extract node information from CodeQL result."""
        if key not in result:
            return None
        return result[key]

    def _create_function_node(
        self,
        func_info: Dict[str, Any],
        business_area: str,
        repo_path: str
    ) -> str:
        """Create or get function node."""
        func_name = func_info.get("label", func_info.get("name", "unknown"))
        func_id = f"{business_area}:{repo_path}:function:{func_name}"

        query = """
        MERGE (f:Function {id: $id})
        ON CREATE SET
          f.name = $name,
          f.business_area = $business_area,
          f.repo = $repo,
          f.file_path = $file_path,
          f.line_start = $line_start,
          f.line_end = $line_end
        ON MATCH SET
          f.name = $name,
          f.file_path = $file_path,
          f.line_start = $line_start,
          f.line_end = $line_end
        RETURN f.id as id
        """

        file_path = func_info.get("file", {}).get("value", "") if isinstance(func_info.get("file"), dict) else ""
        line_start = func_info.get("startLine", 0)
        line_end = func_info.get("endLine", 0)

        try:
            result = neo4j_manager.execute_query(query, {
                "id": func_id,
                "name": func_name,
                "business_area": business_area,
                "repo": repo_path,
                "file_path": file_path,
                "line_start": line_start,
                "line_end": line_end
            })
            return func_id
        except Exception as e:
            logger.error("Failed to create function node", error=str(e))
            return func_id

    def _create_script_node(
        self,
        script_path: str,
        business_area: str,
        repo_path: str
    ) -> str:
        """Create or get script node."""
        script_id = f"{business_area}:{repo_path}:script:{script_path}"

        query = """
        MERGE (s:Script {id: $id})
        ON CREATE SET
          s.path = $path,
          s.business_area = $business_area,
          s.repo = $repo
        RETURN s.id as id
        """

        try:
            neo4j_manager.execute_query(query, {
                "id": script_id,
                "path": script_path,
                "business_area": business_area,
                "repo": repo_path
            })
            return script_id
        except Exception as e:
            logger.error("Failed to create script node", error=str(e))
            return script_id

    def _create_file_node(
        self,
        file_info: Dict[str, Any],
        business_area: str,
        repo_path: str
    ) -> str:
        """Create or get file node."""
        file_path = file_info.get("label", file_info.get("value", "unknown"))
        file_id = f"{business_area}:{repo_path}:file:{file_path}"

        query = """
        MERGE (f:File {id: $id})
        ON CREATE SET
          f.file_path = $file_path,
          f.business_area = $business_area,
          f.repo = $repo
        RETURN f.id as id
        """

        try:
            neo4j_manager.execute_query(query, {
                "id": file_id,
                "file_path": file_path,
                "business_area": business_area,
                "repo": repo_path
            })
            return file_id
        except Exception as e:
            logger.error("Failed to create file node", error=str(e))
            return file_id

    def _create_module_node(
        self,
        module_name: str,
        business_area: str,
        repo_path: str
    ) -> str:
        """Create or get module node."""
        module_id = f"{business_area}:{repo_path}:module:{module_name}"

        query = """
        MERGE (m:Module {id: $id})
        ON CREATE SET
          m.name = $name,
          m.business_area = $business_area,
          m.repo = $repo
        RETURN m.id as id
        """

        try:
            neo4j_manager.execute_query(query, {
                "id": module_id,
                "name": module_name,
                "business_area": business_area,
                "repo": repo_path
            })
            return module_id
        except Exception as e:
            logger.error("Failed to create module node", error=str(e))
            return module_id

    def _create_edge(
        self,
        source_id: str,
        edge_type: str,
        target_id: str,
        business_area: str,
        repo_path: str
    ) -> None:
        """Create graph edge."""
        query = f"""
        MATCH (source {{id: $source_id}}), (target {{id: $target_id}})
        MERGE (source)-[r:{edge_type}]->(target)
        ON CREATE SET
          r.business_area = $business_area,
          r.repo = $repo_path
        """

        try:
            neo4j_manager.execute_query(query, {
                "source_id": source_id,
                "target_id": target_id,
                "business_area": business_area,
                "repo_path": repo_path
            })
        except Exception as e:
            logger.error(
                "Failed to create edge",
                source=source_id,
                edge_type=edge_type,
                target=target_id,
                error=str(e)
            )


# Global graph emitter instance
graph_emitter = GraphEmitter()

