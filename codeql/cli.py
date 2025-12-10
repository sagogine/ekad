"""CodeQL CLI wrapper for building databases and executing queries."""
import subprocess
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from core.logging import get_logger

logger = get_logger(__name__)


class CodeQLCLI:
    """Wrapper for CodeQL CLI operations."""

    def __init__(self, codeql_path: Optional[str] = None):
        """
        Initialize CodeQL CLI wrapper.

        Args:
            codeql_path: Path to CodeQL executable (defaults to "codeql" in PATH)
        """
        self.codeql_path = codeql_path or self._find_codeql()
        if not self.codeql_path:
            raise ValueError(
                "CodeQL CLI not found. Install from https://github.com/github/codeql-cli-binaries "
                "or set CODEQL_PATH environment variable."
            )
        logger.info("CodeQL CLI initialized", path=self.codeql_path)

    def _find_codeql(self) -> Optional[str]:
        """Find CodeQL executable in PATH."""
        codeql_path = shutil.which("codeql")
        if codeql_path:
            return codeql_path

        # Check common installation locations
        common_paths = [
            "/usr/local/bin/codeql",
            "/opt/codeql/codeql",
            Path.home() / "codeql-home" / "codeql" / "codeql",
        ]

        for path in common_paths:
            if Path(path).exists():
                return str(path)

        return None

    def _run_command(
        self,
        args: List[str],
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None
    ) -> subprocess.CompletedProcess:
        """
        Run CodeQL command.

        Args:
            args: Command arguments
            cwd: Working directory
            timeout: Command timeout in seconds

        Returns:
            CompletedProcess result
        """
        cmd = [self.codeql_path] + args
        logger.debug("Running CodeQL command", command=" ".join(cmd[:3]))

        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False  # We'll check return code manually
            )

            if result.returncode != 0:
                logger.error(
                    "CodeQL command failed",
                    command=" ".join(cmd[:3]),
                    returncode=result.returncode,
                    stderr=result.stderr[:500] if result.stderr else None
                )
                raise subprocess.CalledProcessError(
                    result.returncode,
                    cmd,
                    result.stdout,
                    result.stderr
                )

            return result

        except subprocess.TimeoutExpired as e:
            logger.error("CodeQL command timed out", command=" ".join(cmd[:3]), timeout=timeout)
            raise
        except FileNotFoundError:
            logger.error("CodeQL executable not found", path=self.codeql_path)
            raise

    def database_create(
        self,
        database_path: str,
        source_path: str,
        language: str,
        command: Optional[str] = None
    ) -> str:
        """
        Create a CodeQL database.

        Args:
            database_path: Path where database will be created
            source_path: Path to source code
            language: Language (python, java, javascript, etc.)
            command: Optional build command (e.g., "mvn compile", "python setup.py build")

        Returns:
            Path to created database
        """
        db_path = Path(database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        args = [
            "database",
            "create",
            str(db_path),
            "--language", language,
            "--source-root", str(source_path)
        ]

        if command:
            args.extend(["--command", command])

        logger.info(
            "Creating CodeQL database",
            database_path=str(db_path),
            source_path=str(source_path),
            language=language
        )

        self._run_command(args, cwd=source_path, timeout=3600)  # 1 hour timeout

        logger.info("CodeQL database created", database_path=str(db_path))
        return str(db_path)

    def database_upgrade(self, database_path: str) -> None:
        """
        Upgrade a CodeQL database to latest format.

        Args:
            database_path: Path to database
        """
        args = ["database", "upgrade", str(database_path)]
        logger.info("Upgrading CodeQL database", database_path=str(database_path))
        self._run_command(args, timeout=600)  # 10 minute timeout

    def query_run(
        self,
        database_path: str,
        query_file: str,
        output_path: Optional[str] = None,
        format: str = "json"
    ) -> Dict[str, Any]:
        """
        Run a CodeQL query against a database.

        Args:
            database_path: Path to CodeQL database
            query_file: Path to .ql query file
            output_path: Optional path to save results
            format: Output format (json, csv, sarif)

        Returns:
            Query results as dictionary (if format=json)
        """
        args = [
            "query",
            "run",
            "--database", str(database_path),
            "--format", format
        ]

        if output_path:
            args.extend(["--output", str(output_path)])

        args.append(str(query_file))

        logger.info(
            "Running CodeQL query",
            database=str(database_path),
            query=str(query_file)
        )

        result = self._run_command(args, timeout=300)  # 5 minute timeout

        if format == "json" and result.stdout:
            import json
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON results, returning raw output")
                return {"raw_output": result.stdout}

        return {"output": result.stdout}

    def get_current_commit(self, repo_path: str) -> Optional[str]:
        """
        Get current Git commit hash for a repository.

        Args:
            repo_path: Path to Git repository

        Returns:
            Commit hash or None if not a Git repo
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def is_codeql_available(self) -> bool:
        """
        Check if CodeQL CLI is available.

        Returns:
            True if CodeQL is available
        """
        try:
            result = self._run_command(["version"], timeout=10)
            logger.info("CodeQL version check", output=result.stdout[:100])
            return True
        except Exception as e:
            logger.warning("CodeQL not available", error=str(e))
            return False


# Global CodeQL CLI instance (lazy initialization)
_codeql_cli: Optional[CodeQLCLI] = None


def get_codeql_cli() -> Optional[CodeQLCLI]:
    """
    Get CodeQL CLI instance.

    Returns:
        CodeQLCLI instance or None if not available
    """
    global _codeql_cli

    if _codeql_cli is None:
        try:
            _codeql_cli = CodeQLCLI()
            if not _codeql_cli.is_codeql_available():
                _codeql_cli = None
        except Exception as e:
            logger.warning("Failed to initialize CodeQL CLI", error=str(e))
            _codeql_cli = None

    return _codeql_cli

