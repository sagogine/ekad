"""GitLab connector for fetching code, wikis, and issues."""
from typing import List, Optional
from datetime import datetime
import gitlab
from ingestion.base import BaseConnector, Document, DocumentType, SourceType
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class GitLabConnector(BaseConnector):
    """Connector for GitLab repositories."""
    
    def __init__(self, business_area: str, project_path: str):
        """
        Initialize GitLab connector.
        
        Args:
            business_area: Business area identifier
            project_path: GitLab project path (e.g., 'group/project')
        """
        super().__init__(business_area)
        self.project_path = project_path
        
        if not settings.gitlab_token:
            raise ValueError("GitLab token not configured")
        
        # Initialize GitLab client
        self.client = gitlab.Gitlab(
            settings.gitlab_url,
            private_token=settings.gitlab_token
        )
        self.client.auth()
        
        # Get project
        self.project = self.client.projects.get(project_path)
        
        logger.info(
            "GitLab connector initialized",
            business_area=business_area,
            project=project_path
        )
    
    def _parse_file(self, file_data: dict, branch: str = 'main') -> Optional[Document]:
        """
        Parse GitLab file to Document.
        
        Args:
            file_data: File data from GitLab
            branch: Branch name
            
        Returns:
            Document object or None if file should be skipped
        """
        file_path = file_data['path']
        file_name = file_data['name']
        
        # Skip non-code files
        code_extensions = ['.py', '.js', '.ts', '.java', '.go', '.rb', '.php', '.cpp', '.c', '.h']
        if not any(file_name.endswith(ext) for ext in code_extensions):
            return None
        
        try:
            # Get file content
            file_obj = self.project.files.get(file_path=file_path, ref=branch)
            content = file_obj.decode().decode('utf-8')
            
            # Get last commit for this file
            commits = self.project.commits.list(path=file_path, per_page=1)
            last_modified = datetime.utcnow()
            if commits:
                last_modified = datetime.fromisoformat(
                    commits[0].committed_date.replace('Z', '+00:00')
                )
            
            # Build URL
            url = f"{settings.gitlab_url}/{self.project_path}/-/blob/{branch}/{file_path}"
            
            return Document(
                id=f"gitlab_{self.project_path.replace('/', '_')}_{file_path.replace('/', '_')}",
                content=content,
                title=f"Code: {file_name}",
                source=SourceType.GITLAB,
                document_type=DocumentType.CODE,
                business_area=self.business_area,
                last_modified=last_modified,
                url=url,
                metadata={
                    "project": self.project_path,
                    "file_path": file_path,
                    "branch": branch,
                    "file_type": file_name.split('.')[-1] if '.' in file_name else 'unknown'
                }
            )
        except Exception as e:
            logger.error(
                "Failed to fetch file content",
                file_path=file_path,
                error=str(e)
            )
            return None
    
    def _parse_issue(self, issue) -> Document:
        """
        Parse GitLab issue to Document.
        
        Args:
            issue: GitLab issue object
            
        Returns:
            Document object
        """
        issue_id = issue.iid
        title = issue.title
        description = issue.description or ""
        
        # Combine title and description
        content = f"# {title}\n\n{description}"
        
        # Get timestamps
        updated_at = datetime.fromisoformat(issue.updated_at.replace('Z', '+00:00'))
        
        # Build URL
        url = f"{settings.gitlab_url}/{self.project_path}/-/issues/{issue_id}"
        
        return Document(
            id=f"gitlab_{self.project_path.replace('/', '_')}_issue_{issue_id}",
            content=content,
            title=f"Issue #{issue_id}: {title}",
            source=SourceType.GITLAB,
            document_type=DocumentType.ISSUE,
            business_area=self.business_area,
            last_modified=updated_at,
            url=url,
            metadata={
                "project": self.project_path,
                "issue_id": issue_id,
                "state": issue.state,
                "labels": issue.labels,
                "author": issue.author.get('name', 'Unknown')
            }
        )
    
    def _parse_wiki(self, wiki) -> Document:
        """
        Parse GitLab wiki page to Document.
        
        Args:
            wiki: GitLab wiki object
            
        Returns:
            Document object
        """
        slug = wiki.slug
        title = wiki.title
        content = wiki.content
        
        # Build URL
        url = f"{settings.gitlab_url}/{self.project_path}/-/wikis/{slug}"
        
        return Document(
            id=f"gitlab_{self.project_path.replace('/', '_')}_wiki_{slug}",
            content=content,
            title=f"Wiki: {title}",
            source=SourceType.GITLAB,
            document_type=DocumentType.WIKI,
            business_area=self.business_area,
            last_modified=datetime.utcnow(),  # Wiki doesn't have last_modified
            url=url,
            metadata={
                "project": self.project_path,
                "slug": slug
            }
        )
    
    async def fetch_all(self) -> List[Document]:
        """
        Fetch all documents from GitLab project.
        
        Returns:
            List of documents
        """
        try:
            logger.info(
                "Fetching all GitLab documents",
                project=self.project_path
            )
            
            documents = []
            
            # Fetch repository files
            try:
                tree = self.project.repository_tree(recursive=True, all=True)
                for item in tree:
                    if item['type'] == 'blob':  # File
                        doc = self._parse_file(item)
                        if doc:
                            documents.append(doc)
            except Exception as e:
                logger.error("Failed to fetch repository files", error=str(e))
            
            # Fetch issues
            try:
                issues = self.project.issues.list(all=True)
                for issue in issues:
                    try:
                        doc = self._parse_issue(issue)
                        documents.append(doc)
                    except Exception as e:
                        logger.error(
                            "Failed to parse issue",
                            issue_id=issue.iid,
                            error=str(e)
                        )
            except Exception as e:
                logger.error("Failed to fetch issues", error=str(e))
            
            # Fetch wiki pages
            try:
                wikis = self.project.wikis.list(all=True)
                for wiki in wikis:
                    try:
                        doc = self._parse_wiki(wiki)
                        documents.append(doc)
                    except Exception as e:
                        logger.error(
                            "Failed to parse wiki",
                            slug=wiki.slug,
                            error=str(e)
                        )
            except Exception as e:
                logger.error("Failed to fetch wikis", error=str(e))
            
            logger.info(
                "Fetched GitLab documents",
                project=self.project_path,
                count=len(documents)
            )
            return documents
        
        except Exception as e:
            logger.error(
                "Failed to fetch GitLab documents",
                project=self.project_path,
                error=str(e)
            )
            raise
    
    async def fetch_since(self, timestamp: datetime) -> List[Document]:
        """
        Fetch documents modified since timestamp.
        
        Args:
            timestamp: Last sync timestamp
            
        Returns:
            List of modified documents
        """
        try:
            logger.info(
                "Fetching modified GitLab documents",
                project=self.project_path,
                since=timestamp.isoformat()
            )
            
            documents = []
            
            # Fetch commits since timestamp
            commits = self.project.commits.list(since=timestamp.isoformat(), all=True)
            
            # Get modified files from commits
            modified_files = set()
            for commit in commits:
                diff = commit.diff()
                for file_diff in diff:
                    if file_diff.get('new_file') or file_diff.get('renamed_file'):
                        modified_files.add(file_diff['new_path'])
                    elif not file_diff.get('deleted_file'):
                        modified_files.add(file_diff['old_path'])
            
            # Fetch modified files
            for file_path in modified_files:
                try:
                    file_data = {'path': file_path, 'name': file_path.split('/')[-1]}
                    doc = self._parse_file(file_data)
                    if doc:
                        documents.append(doc)
                except Exception as e:
                    logger.error(
                        "Failed to fetch modified file",
                        file_path=file_path,
                        error=str(e)
                    )
            
            # Fetch issues updated since timestamp
            try:
                issues = self.project.issues.list(
                    updated_after=timestamp.isoformat(),
                    all=True
                )
                for issue in issues:
                    try:
                        doc = self._parse_issue(issue)
                        documents.append(doc)
                    except Exception as e:
                        logger.error(
                            "Failed to parse issue",
                            issue_id=issue.iid,
                            error=str(e)
                        )
            except Exception as e:
                logger.error("Failed to fetch updated issues", error=str(e))
            
            logger.info(
                "Fetched modified GitLab documents",
                project=self.project_path,
                count=len(documents)
            )
            return documents
        
        except Exception as e:
            logger.error(
                "Failed to fetch modified GitLab documents",
                project=self.project_path,
                error=str(e)
            )
            raise
    
    async def get_all_document_ids(self) -> List[str]:
        """
        Get all current document IDs.
        
        Returns:
            List of document IDs
        """
        try:
            document_ids = []
            
            # Get file IDs
            tree = self.project.repository_tree(recursive=True, all=True)
            for item in tree:
                if item['type'] == 'blob':
                    file_path = item['path']
                    doc_id = f"gitlab_{self.project_path.replace('/', '_')}_{file_path.replace('/', '_')}"
                    document_ids.append(doc_id)
            
            # Get issue IDs
            issues = self.project.issues.list(all=True)
            for issue in issues:
                doc_id = f"gitlab_{self.project_path.replace('/', '_')}_issue_{issue.iid}"
                document_ids.append(doc_id)
            
            # Get wiki IDs
            wikis = self.project.wikis.list(all=True)
            for wiki in wikis:
                doc_id = f"gitlab_{self.project_path.replace('/', '_')}_wiki_{wiki.slug}"
                document_ids.append(doc_id)
            
            logger.debug(
                "Retrieved GitLab document IDs",
                project=self.project_path,
                count=len(document_ids)
            )
            return document_ids
        
        except Exception as e:
            logger.error(
                "Failed to get GitLab document IDs",
                project=self.project_path,
                error=str(e)
            )
            raise
