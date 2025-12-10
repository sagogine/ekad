"""OpenMetadata connector for fetching data lineage and asset metadata."""
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, UTC
from ingestion.base import BaseConnector, Document, DocumentType, SourceType
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class OpenMetadataConnector(BaseConnector):
    """Connector for OpenMetadata API."""
    
    def __init__(self, business_area: str, service_name: str, api_url: str = None, api_token: str = None):
        """
        Initialize OpenMetadata connector.
        
        Args:
            business_area: Business area identifier
            service_name: OpenMetadata service name (e.g., 'datahub', 'snowflake')
            api_url: OpenMetadata API URL (defaults to env or common defaults)
            api_token: API token for authentication
        """
        super().__init__(business_area)
        self.service_name = service_name
        self.api_url = api_url or settings.openmetadata_url
        # Handle both SecretStr from settings and plain string from override
        if api_token:
            self.api_token = api_token
        else:
            self.api_token = settings.get_secret_value(settings.openmetadata_token, field_name="openmetadata_token")
        
        self.client = httpx.AsyncClient(
            base_url=self.api_url,
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {self.api_token}"} if self.api_token else {})
            },
            timeout=30.0
        )
        
        logger.info(
            "OpenMetadata connector initialized",
            business_area=business_area,
            service=service_name,
            api_url=self.api_url
        )
    
    async def fetch_all(self) -> List[Document]:
        """Fetch all lineage and metadata from OpenMetadata."""
        logger.info("Fetching all OpenMetadata assets", business_area=self.business_area)
        
        documents = []
        
        # Fetch tables/datasets
        try:
            tables = await self._fetch_tables()
            for table in tables:
                docs = self._table_to_documents(table)
                documents.extend(docs)
        except Exception as e:
            logger.error("Failed to fetch tables", error=str(e))
        
        # Fetch pipelines/workflows
        try:
            pipelines = await self._fetch_pipelines()
            for pipeline in pipelines:
                docs = self._pipeline_to_documents(pipeline)
                documents.extend(docs)
        except Exception as e:
            logger.error("Failed to fetch pipelines", error=str(e))
        
        # Fetch lineage relationships
        try:
            lineage_docs = await self._fetch_lineage()
            documents.extend(lineage_docs)
        except Exception as e:
            logger.error("Failed to fetch lineage", error=str(e))
        
        logger.info(
            "OpenMetadata fetch completed",
            business_area=self.business_area,
            documents=len(documents)
        )
        
        return documents
    
    async def fetch_since(self, timestamp: datetime) -> List[Document]:
        """Fetch assets modified since timestamp."""
        logger.info(
            "Fetching modified OpenMetadata assets",
            business_area=self.business_area,
            since=timestamp.isoformat()
        )
        
        # OpenMetadata API typically doesn't support time-based filtering well
        # So we fetch all and filter client-side
        all_docs = await self.fetch_all()
        
        filtered = [
            doc for doc in all_docs
            if doc.last_modified >= timestamp
        ]
        
        return filtered
    
    async def get_all_document_ids(self) -> List[str]:
        """Get all document IDs."""
        all_docs = await self.fetch_all()
        return [doc.id for doc in all_docs]
    
    async def _fetch_tables(self) -> List[Dict[str, Any]]:
        """Fetch table/dataset metadata."""
        try:
            response = await self.client.get(
                "/tables",
                params={"service": self.service_name, "limit": 1000}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except Exception as e:
            logger.error("Failed to fetch tables from OpenMetadata", error=str(e))
            return []
    
    async def _fetch_pipelines(self) -> List[Dict[str, Any]]:
        """Fetch pipeline/workflow metadata."""
        try:
            response = await self.client.get(
                "/pipelines",
                params={"service": self.service_name, "limit": 1000}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except Exception as e:
            logger.error("Failed to fetch pipelines from OpenMetadata", error=str(e))
            return []
    
    async def _fetch_lineage(self) -> List[Document]:
        """Fetch lineage relationships and create documents."""
        documents = []
        
        try:
            # Fetch lineage for tables
            tables = await self._fetch_tables()
            for table in tables:
                table_fqn = table.get("fullyQualifiedName", "")
                if not table_fqn:
                    continue
                
                try:
                    response = await self.client.get(f"/lineage/table/name/{table_fqn}")
                    response.raise_for_status()
                    lineage_data = response.json()
                    
                    # Create lineage document
                    lineage_doc = self._lineage_to_document(table_fqn, lineage_data)
                    if lineage_doc:
                        documents.append(lineage_doc)
                except Exception as e:
                    logger.debug(
                        "Failed to fetch lineage for table",
                        table=table_fqn,
                        error=str(e)
                    )
        except Exception as e:
            logger.error("Failed to fetch lineage", error=str(e))
        
        return documents
    
    def _table_to_documents(self, table: Dict[str, Any]) -> List[Document]:
        """Convert table metadata to documents."""
        docs = []
        
        table_fqn = table.get("fullyQualifiedName", "")
        table_name = table.get("name", "")
        description = table.get("description", "")
        columns = table.get("columns", [])
        
        # Main table document
        table_doc = Document(
            id=f"om_table_{table_fqn.replace('.', '_').replace('/', '_')}",
            content=f"Table: {table_name}\n\n{description}\n\nColumns:\n" + "\n".join(
                f"- {col.get('name', '')}: {col.get('dataType', '')} - {col.get('description', '')}"
                for col in columns[:50]  # Limit columns
            ),
            title=f"Table: {table_name}",
            source=SourceType.OPENMETADATA,
            document_type=DocumentType.OTHER,
            business_area=self.business_area,
            last_modified=datetime.fromisoformat(
                table.get("updatedAt", datetime.now(UTC).isoformat()).replace('Z', '+00:00')
            ) if table.get("updatedAt") else datetime.now(UTC),
            url=f"{self.api_url}/table/{table_fqn}" if table_fqn else "",
            metadata={
                "asset_type": "table",
                "fully_qualified_name": table_fqn,
                "service": self.service_name,
                "columns_count": len(columns),
                "tags": table.get("tags", [])
            }
        )
        docs.append(table_doc)
        
        return docs
    
    def _pipeline_to_documents(self, pipeline: Dict[str, Any]) -> List[Document]:
        """Convert pipeline metadata to documents."""
        pipeline_fqn = pipeline.get("fullyQualifiedName", "")
        pipeline_name = pipeline.get("name", "")
        description = pipeline.get("description", "")
        tasks = pipeline.get("tasks", [])
        
        doc = Document(
            id=f"om_pipeline_{pipeline_fqn.replace('.', '_').replace('/', '_')}",
            content=f"Pipeline: {pipeline_name}\n\n{description}\n\nTasks:\n" + "\n".join(
                f"- {task.get('name', '')}: {task.get('taskType', '')}"
                for task in tasks[:50]
            ),
            title=f"Pipeline: {pipeline_name}",
            source=SourceType.OPENMETADATA,
            document_type=DocumentType.OTHER,
            business_area=self.business_area,
            last_modified=datetime.fromisoformat(
                pipeline.get("updatedAt", datetime.now(UTC).isoformat()).replace('Z', '+00:00')
            ) if pipeline.get("updatedAt") else datetime.now(UTC),
            url=f"{self.api_url}/pipeline/{pipeline_fqn}" if pipeline_fqn else "",
            metadata={
                "asset_type": "pipeline",
                "fully_qualified_name": pipeline_fqn,
                "service": self.service_name,
                "tasks_count": len(tasks)
            }
        )
        
        return [doc]
    
    def _lineage_to_document(self, entity_fqn: str, lineage_data: Dict[str, Any]) -> Optional[Document]:
        """Convert lineage data to a document."""
        upstream = lineage_data.get("upstreamEdges", [])
        downstream = lineage_data.get("downstreamEdges", [])
        
        if not upstream and not downstream:
            return None
        
        lineage_text = f"Lineage for: {entity_fqn}\n\n"
        
        if upstream:
            lineage_text += "Upstream dependencies:\n"
            for edge in upstream[:20]:  # Limit edges
                from_entity = edge.get("fromEntity", "")
                lineage_text += f"- {from_entity}\n"
        
        if downstream:
            lineage_text += "\nDownstream dependencies:\n"
            for edge in downstream[:20]:
                to_entity = edge.get("toEntity", "")
                lineage_text += f"- {to_entity}\n"
        
        return Document(
            id=f"om_lineage_{entity_fqn.replace('.', '_').replace('/', '_')}",
            content=lineage_text,
            title=f"Lineage: {entity_fqn}",
            source=SourceType.OPENMETADATA,
            document_type=DocumentType.OTHER,
            business_area=self.business_area,
            last_modified=datetime.now(UTC),
            url=f"{self.api_url}/lineage/table/name/{entity_fqn}",
            metadata={
                "asset_type": "lineage",
                "entity_fqn": entity_fqn,
                "service": self.service_name,
                "upstream_count": len(upstream),
                "downstream_count": len(downstream)
            }
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

