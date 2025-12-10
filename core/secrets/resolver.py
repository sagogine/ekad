"""Secrets resolver that fetches from env vars or secrets manager."""
from typing import Optional
from core.config import settings
from core.secrets.base import SecretProvider, SecretsManager
from core.secrets.gcp_secret_manager import GCPSecretManager
from core.logging import get_logger

logger = get_logger(__name__)

# Global secrets manager instance (lazy initialization)
_secrets_manager: Optional[SecretsManager] = None


def get_secrets_manager() -> Optional[SecretsManager]:
    """
    Get or initialize the secrets manager based on configuration.

    Returns:
        SecretsManager instance or None if not configured
    """
    global _secrets_manager

    if _secrets_manager is not None:
        return _secrets_manager

    provider = settings.secrets_provider

    if provider == "none" or provider == SecretProvider.NONE:
        _secrets_manager = None
        return None

    if provider == "gcp" or provider == SecretProvider.GCP:
        _secrets_manager = GCPSecretManager()
        if not _secrets_manager.is_available():
            logger.warning("GCP Secret Manager not available, falling back to env vars")
            _secrets_manager = None
        return _secrets_manager

    logger.warning(f"Unknown secrets provider: {provider}, falling back to env vars")
    return None


def resolve_secret(
    env_value: Optional[str],
    secret_name: str,
    use_async: bool = False
) -> Optional[str]:
    """
    Resolve a secret value from environment or secrets manager.

    Priority:
    1. Environment variable (if provided and not empty)
    2. Secrets Manager (if configured and available)

    Args:
        env_value: Value from environment variable (may be None or empty)
        secret_name: Name of the secret in Secret Manager
        use_async: Whether to use async method (default: False for sync)

    Returns:
        Secret value or None if not found
    """
    # If env value exists and is not empty, use it
    if env_value and env_value.strip():
        return env_value.strip()

    # Try secrets manager
    secrets_mgr = get_secrets_manager()
    if not secrets_mgr:
        return None

    # Build full secret name with prefix if configured
    full_secret_name = secret_name
    if settings.secrets_path_prefix:
        full_secret_name = f"{settings.secrets_path_prefix}/{secret_name}"

    try:
        if use_async:
            # Note: This would need to be awaited in async context
            # For now, we'll use sync version
            logger.warning("Async secret resolution not yet implemented, using sync")
            return secrets_mgr.get_secret_sync(full_secret_name)
        else:
            return secrets_mgr.get_secret_sync(full_secret_name)
    except Exception as e:
        logger.error(
            "Failed to resolve secret from secrets manager",
            secret_name=full_secret_name,
            error=str(e)
        )
        return None


async def resolve_secret_async(
    env_value: Optional[str],
    secret_name: str
) -> Optional[str]:
    """
    Resolve a secret value asynchronously from environment or secrets manager.

    Priority:
    1. Environment variable (if provided and not empty)
    2. Secrets Manager (if configured and available)

    Args:
        env_value: Value from environment variable (may be None or empty)
        secret_name: Name of the secret in Secret Manager

    Returns:
        Secret value or None if not found
    """
    # If env value exists and is not empty, use it
    if env_value and env_value.strip():
        return env_value.strip()

    # Try secrets manager
    secrets_mgr = get_secrets_manager()
    if not secrets_mgr:
        return None

    # Build full secret name with prefix if configured
    full_secret_name = secret_name
    if settings.secrets_path_prefix:
        full_secret_name = f"{settings.secrets_path_prefix}/{secret_name}"

    try:
        return await secrets_mgr.get_secret(full_secret_name)
    except Exception as e:
        logger.error(
            "Failed to resolve secret from secrets manager (async)",
            secret_name=full_secret_name,
            error=str(e)
        )
        return None

