"""Google Cloud Secret Manager implementation."""
from typing import Optional
from google.cloud import secretmanager
from google.api_core import exceptions as gcp_exceptions
from core.secrets.base import SecretsManager
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class GCPSecretManager(SecretsManager):
    """Google Cloud Secret Manager implementation."""

    def __init__(self, project_id: Optional[str] = None):
        """
        Initialize GCP Secret Manager client.

        Args:
            project_id: GCP project ID (defaults to google_cloud_project from settings)
        """
        self.project_id = project_id or settings.google_cloud_project
        self._client: Optional[secretmanager.SecretManagerServiceClient] = None
        self._available: Optional[bool] = None

        if not self.project_id:
            logger.warning(
                "GCP Secret Manager initialized without project_id. "
                "Set GOOGLE_CLOUD_PROJECT environment variable."
            )
            self._available = False
        else:
            try:
                self._client = secretmanager.SecretManagerServiceClient()
                logger.info(
                    "GCP Secret Manager initialized",
                    project_id=self.project_id
                )
            except Exception as e:
                logger.error(
                    "Failed to initialize GCP Secret Manager",
                    error=str(e)
                )
                self._available = False

    def is_available(self) -> bool:
        """Check if GCP Secret Manager is available."""
        if self._available is not None:
            return self._available

        if not self.project_id or not self._client:
            self._available = False
            return False

        try:
            # Try to access the project to verify credentials
            self._client.project_path(self.project_id)
            self._available = True
            return True
        except Exception as e:
            logger.warning(
                "GCP Secret Manager not available",
                error=str(e)
            )
            self._available = False
            return False

    async def get_secret(self, secret_name: str, version: Optional[str] = None) -> Optional[str]:
        """
        Retrieve a secret value asynchronously.

        Args:
            secret_name: Name of the secret in Secret Manager
            version: Optional version (defaults to "latest")

        Returns:
            Secret value or None if not found
        """
        if not self.is_available():
            return None

        try:
            # Build the resource name of the secret version
            if version:
                name = f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
            else:
                name = f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"

            # Access the secret version
            response = self._client.access_secret_version(request={"name": name})
            secret_value = response.payload.data.decode("UTF-8")

            logger.debug(
                "Retrieved secret from GCP Secret Manager",
                secret_name=secret_name,
                version=version or "latest"
            )

            return secret_value

        except gcp_exceptions.NotFound:
            logger.warning(
                "Secret not found in GCP Secret Manager",
                secret_name=secret_name,
                version=version or "latest"
            )
            return None
        except Exception as e:
            logger.error(
                "Failed to retrieve secret from GCP Secret Manager",
                secret_name=secret_name,
                error=str(e)
            )
            return None

    def get_secret_sync(self, secret_name: str, version: Optional[str] = None) -> Optional[str]:
        """
        Retrieve a secret value synchronously.

        Args:
            secret_name: Name of the secret in Secret Manager
            version: Optional version (defaults to "latest")

        Returns:
            Secret value or None if not found
        """
        if not self.is_available():
            return None

        try:
            # Build the resource name of the secret version
            if version:
                name = f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
            else:
                name = f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"

            # Access the secret version
            response = self._client.access_secret_version(request={"name": name})
            secret_value = response.payload.data.decode("UTF-8")

            logger.debug(
                "Retrieved secret from GCP Secret Manager (sync)",
                secret_name=secret_name,
                version=version or "latest"
            )

            return secret_value

        except gcp_exceptions.NotFound:
            logger.warning(
                "Secret not found in GCP Secret Manager (sync)",
                secret_name=secret_name,
                version=version or "latest"
            )
            return None
        except Exception as e:
            logger.error(
                "Failed to retrieve secret from GCP Secret Manager (sync)",
                secret_name=secret_name,
                error=str(e)
            )
            return None

