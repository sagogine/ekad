"""Base interface for secrets management."""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional


class SecretProvider(str, Enum):
    """Supported secret provider types."""
    NONE = "none"  # Use environment variables only
    GCP = "gcp"  # Google Cloud Secret Manager
    # Future providers:
    # AWS = "aws"  # AWS Secrets Manager
    # VAULT = "vault"  # HashiCorp Vault
    # AZURE = "azure"  # Azure Key Vault


class SecretsManager(ABC):
    """Abstract base class for secrets management providers."""

    @abstractmethod
    async def get_secret(self, secret_name: str, version: Optional[str] = None) -> Optional[str]:
        """
        Retrieve a secret value by name.

        Args:
            secret_name: Name/identifier of the secret
            version: Optional version identifier (provider-specific)

        Returns:
            Secret value as string, or None if not found
        """
        pass

    @abstractmethod
    async def get_secret_sync(self, secret_name: str, version: Optional[str] = None) -> Optional[str]:
        """
        Retrieve a secret value by name (synchronous).

        Args:
            secret_name: Name/identifier of the secret
            version: Optional version identifier (provider-specific)

        Returns:
            Secret value as string, or None if not found
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the secrets manager is available and configured.

        Returns:
            True if available, False otherwise
        """
        pass

