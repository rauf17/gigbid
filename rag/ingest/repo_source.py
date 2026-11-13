"""Repository ingestion source interface and local filesystem implementation."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar


@dataclass
class RepoFile:
    """Represents a file discovered within a persona code repository."""
    repo_name: str
    relative_path: str
    content: str
    is_readme: bool
    language: str


class RepoSource(ABC):
    """Abstract interface for accessing persona code repositories."""

    @abstractmethod
    def list_repos(self, persona_dir: Path) -> list[str]:
        """List repository directory names under the persona."""

    @abstractmethod
    def get_repo_files(self, persona_dir: Path, repo_name: str) -> list[RepoFile]:
        """Retrieve all ingestible code and documentation files for a repository."""


class LocalRepoSource(RepoSource):
    """Reads repository files directly from the local persona folder structure."""

    SUPPORTED_EXTENSIONS: ClassVar[dict[str, str]] = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".sql": "sql",
        ".sh": "bash",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".json": "json",
        ".md": "markdown",
    }

    def list_repos(self, persona_dir: Path) -> list[str]:
        repos_dir = persona_dir / "repos"
        if not repos_dir.is_dir():
            return []
        return [d.name for d in repos_dir.iterdir() if d.is_dir()]

    def get_repo_files(self, persona_dir: Path, repo_name: str) -> list[RepoFile]:
        repo_dir = persona_dir / "repos" / repo_name
        if not repo_dir.is_dir():
            return []

        files: list[RepoFile] = []
        for path in sorted(repo_dir.rglob("*")):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or ".git" in path.parts:
                continue

            rel = path.relative_to(repo_dir).as_posix()
            is_readme = path.name.lower() == "readme.md"
            ext = path.suffix.lower()

            if is_readme:
                language = "markdown"
            elif ext in self.SUPPORTED_EXTENSIONS:
                language = self.SUPPORTED_EXTENSIONS[ext]
            else:
                continue

            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            files.append(
                RepoFile(
                    repo_name=repo_name,
                    relative_path=rel,
                    content=content,
                    is_readme=is_readme,
                    language=language,
                )
            )
        return files
