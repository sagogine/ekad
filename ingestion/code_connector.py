"""Code connector for parsing SQL/Python/Java files into logical units."""
import ast
import re
from typing import List, Optional, Dict, Any
from datetime import datetime
from ingestion.base import BaseConnector, Document, DocumentType, SourceType
from ingestion.gitlab import GitLabConnector
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class CodeConnector(BaseConnector):
    """Connector for code files that parses them into logical units."""
    
    def __init__(self, business_area: str, source_config: Dict[str, Any]):
        """
        Initialize code connector.
        
        Args:
            business_area: Business area identifier
            source_config: Configuration dict with 'source' (gitlab/filesystem) and source-specific params
        """
        super().__init__(business_area)
        self.source_type = source_config.get("source", "gitlab")
        self.source_config = source_config
        
        # Initialize underlying connector if needed
        if self.source_type == "gitlab":
            project_path = source_config.get("project_path")
            if not project_path:
                raise ValueError("GitLab code connector requires 'project_path' in config")
            self.gitlab_connector = GitLabConnector(business_area, project_path)
        else:
            raise ValueError(f"Unsupported code source type: {self.source_type}")
        
        # Language filters
        self.languages = source_config.get("languages", ["python", "java", "sql"])
        if isinstance(self.languages, str):
            self.languages = [lang.strip() for lang in self.languages.split("|")]
        
        logger.info(
            "Code connector initialized",
            business_area=business_area,
            source=self.source_type,
            languages=self.languages
        )
    
    async def fetch_all(self) -> List[Document]:
        """Fetch all code files and parse them into logical units."""
        logger.info("Fetching all code files", business_area=self.business_area)
        
        if self.source_type == "gitlab":
            # Get raw files from GitLab
            raw_docs = await self.gitlab_connector.fetch_all()
        else:
            raw_docs = []
        
        # Parse code files into logical units
        parsed_docs = []
        for doc in raw_docs:
            if doc.document_type != DocumentType.CODE:
                continue
            
            file_type = doc.metadata.get("file_type", "").lower()
            if not self._is_supported_language(file_type):
                continue
            
            try:
                units = self._parse_code_file(doc)
                parsed_docs.extend(units)
            except Exception as e:
                logger.error(
                    "Failed to parse code file",
                    file_path=doc.metadata.get("file_path", ""),
                    error=str(e)
                )
        
        logger.info(
            "Code parsing completed",
            business_area=self.business_area,
            files_parsed=len(raw_docs),
            units_created=len(parsed_docs)
        )
        
        return parsed_docs
    
    async def fetch_since(self, timestamp: datetime) -> List[Document]:
        """Fetch modified code files since timestamp."""
        logger.info(
            "Fetching modified code files",
            business_area=self.business_area,
            since=timestamp.isoformat()
        )
        
        if self.source_type == "gitlab":
            raw_docs = await self.gitlab_connector.fetch_since(timestamp)
        else:
            raw_docs = []
        
        parsed_docs = []
        for doc in raw_docs:
            if doc.document_type != DocumentType.CODE:
                continue
            
            file_type = doc.metadata.get("file_type", "").lower()
            if not self._is_supported_language(file_type):
                continue
            
            try:
                units = self._parse_code_file(doc)
                parsed_docs.extend(units)
            except Exception as e:
                logger.error(
                    "Failed to parse code file",
                    file_path=doc.metadata.get("file_path", ""),
                    error=str(e)
                )
        
        return parsed_docs
    
    async def get_all_document_ids(self) -> List[str]:
        """Get all document IDs from underlying source."""
        if self.source_type == "gitlab":
            return await self.gitlab_connector.get_all_document_ids()
        return []
    
    def _is_supported_language(self, file_type: str) -> bool:
        """Check if file type is in supported languages."""
        lang_map = {
            "py": "python",
            "java": "java",
            "sql": "sql",
            "js": "javascript",
            "ts": "typescript"
        }
        normalized = lang_map.get(file_type, file_type)
        return normalized in self.languages
    
    def _parse_code_file(self, doc: Document) -> List[Document]:
        """
        Parse a code file into logical units (functions, classes, SQL statements).
        
        Args:
            doc: Original code file document
            
        Returns:
            List of documents, one per logical unit
        """
        file_type = doc.metadata.get("file_type", "").lower()
        content = doc.content
        
        if file_type == "py":
            return self._parse_python(doc, content)
        elif file_type == "java":
            return self._parse_java(doc, content)
        elif file_type == "sql":
            return self._parse_sql(doc, content)
        else:
            # Fallback: return original document
            return [doc]
    
    def _parse_python(self, doc: Document, content: str) -> List[Document]:
        """Parse Python file into functions and classes."""
        units = []
        
        try:
            tree = ast.parse(content)
            base_id = doc.id
            file_path = doc.metadata.get("file_path", "")
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Extract function
                    func_code = ast.get_source_segment(content, node) or ""
                    func_doc = self._create_code_unit(
                        base_doc=doc,
                        unit_name=node.name,
                        unit_type="function",
                        content=func_code,
                        line_start=node.lineno,
                        line_end=node.end_lineno if hasattr(node, 'end_lineno') else node.lineno,
                        unit_id=f"{base_id}_func_{node.name}"
                    )
                    units.append(func_doc)
                
                elif isinstance(node, ast.ClassDef):
                    # Extract class
                    class_code = ast.get_source_segment(content, node) or ""
                    class_doc = self._create_code_unit(
                        base_doc=doc,
                        unit_name=node.name,
                        unit_type="class",
                        content=class_code,
                        line_start=node.lineno,
                        line_end=node.end_lineno if hasattr(node, 'end_lineno') else node.lineno,
                        unit_id=f"{base_id}_class_{node.name}"
                    )
                    units.append(class_doc)
        
        except SyntaxError as e:
            logger.warning(
                "Python syntax error; returning file as-is",
                file_path=doc.metadata.get("file_path", ""),
                error=str(e)
            )
            return [doc]
        
        # If no units extracted, return original
        return units if units else [doc]
    
    def _parse_java(self, doc: Document, content: str) -> List[Document]:
        """Parse Java file into methods and classes."""
        units = []
        base_id = doc.id
        
        # Extract classes
        class_pattern = r'(?:public\s+)?(?:abstract\s+)?(?:final\s+)?class\s+(\w+)[^{]*\{'
        for match in re.finditer(class_pattern, content):
            class_name = match.group(1)
            # Find matching brace (simplified)
            start_pos = match.start()
            brace_count = 0
            end_pos = start_pos
            
            for i, char in enumerate(content[start_pos:], start_pos):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = i + 1
                        break
            
            class_code = content[start_pos:end_pos]
            class_doc = self._create_code_unit(
                base_doc=doc,
                unit_name=class_name,
                unit_type="class",
                content=class_code,
                line_start=content[:start_pos].count('\n') + 1,
                line_end=content[:end_pos].count('\n') + 1,
                unit_id=f"{base_id}_class_{class_name}"
            )
            units.append(class_doc)
        
        # Extract methods (simplified regex)
        method_pattern = r'(?:public|private|protected)\s+\w+\s+(\w+)\s*\([^)]*\)\s*\{'
        for match in re.finditer(method_pattern, content):
            method_name = match.group(1)
            start_pos = match.start()
            # Find method body (simplified)
            brace_count = 0
            end_pos = start_pos
            
            for i, char in enumerate(content[start_pos:], start_pos):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = i + 1
                        break
            
            method_code = content[start_pos:end_pos]
            method_doc = self._create_code_unit(
                base_doc=doc,
                unit_name=method_name,
                unit_type="method",
                content=method_code,
                line_start=content[:start_pos].count('\n') + 1,
                line_end=content[:end_pos].count('\n') + 1,
                unit_id=f"{base_id}_method_{method_name}"
            )
            units.append(method_doc)
        
        return units if units else [doc]
    
    def _parse_sql(self, doc: Document, content: str) -> List[Document]:
        """Parse SQL file into individual statements."""
        units = []
        base_id = doc.id
        
        # Split by semicolons and clean
        statements = re.split(r';\s*\n', content)
        
        for idx, statement in enumerate(statements):
            statement = statement.strip()
            if not statement or len(statement) < 10:  # Skip very short statements
                continue
            
            # Extract statement type
            stmt_type = "query"
            if re.match(r'^\s*CREATE\s+TABLE', statement, re.IGNORECASE):
                stmt_type = "create_table"
            elif re.match(r'^\s*SELECT', statement, re.IGNORECASE):
                stmt_type = "select"
            elif re.match(r'^\s*INSERT', statement, re.IGNORECASE):
                stmt_type = "insert"
            elif re.match(r'^\s*UPDATE', statement, re.IGNORECASE):
                stmt_type = "update"
            elif re.match(r'^\s*DELETE', statement, re.IGNORECASE):
                stmt_type = "delete"
            
            sql_doc = self._create_code_unit(
                base_doc=doc,
                unit_name=f"statement_{idx + 1}",
                unit_type=stmt_type,
                content=statement,
                line_start=0,
                line_end=0,
                unit_id=f"{base_id}_sql_{idx + 1}"
            )
            units.append(sql_doc)
        
        return units if units else [doc]
    
    def _create_code_unit(
        self,
        base_doc: Document,
        unit_name: str,
        unit_type: str,
        content: str,
        line_start: int,
        line_end: int,
        unit_id: str
    ) -> Document:
        """Create a document for a code unit."""
        file_path = base_doc.metadata.get("file_path", "")
        file_name = base_doc.metadata.get("file_name", file_path.split("/")[-1])
        
        return Document(
            id=unit_id,
            content=content,
            title=f"{unit_type.title()}: {unit_name} ({file_name})",
            source=SourceType.CODE,
            document_type=DocumentType.CODE,
            business_area=self.business_area,
            last_modified=base_doc.last_modified,
            url=f"{base_doc.url}#L{line_start}-L{line_end}" if line_start > 0 else base_doc.url,
            metadata={
                **base_doc.metadata,
                "unit_name": unit_name,
                "unit_type": unit_type,
                "line_start": line_start,
                "line_end": line_end,
                "file_name": file_name
            }
        )

