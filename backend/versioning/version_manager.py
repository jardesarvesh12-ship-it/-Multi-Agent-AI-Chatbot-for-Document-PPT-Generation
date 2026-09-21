"""
version_manager.py — Document and PPT version management.
Tracks all generated file versions with metadata, timestamps and diffs.
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from backend.config import settings


class VersionRecord:
    """Represents a single version of a generated artifact."""

    def __init__(
        self,
        artifact_id: str,
        version_number: int,
        file_path: str,
        file_type: str,  # "docx" or "pptx"
        title: str,
        description: str = "",
        parent_version: Optional[int] = None,
        metadata: Optional[dict] = None,
    ):
        self.artifact_id = artifact_id
        self.version_number = version_number
        self.file_path = file_path
        self.file_type = file_type
        self.title = title
        self.description = description
        self.parent_version = parent_version
        self.metadata = metadata or {}
        self.created_at = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> dict:
        return {
            "artifact_id": self.artifact_id,
            "version_number": self.version_number,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "title": self.title,
            "description": self.description,
            "parent_version": self.parent_version,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VersionRecord":
        rec = cls(
            artifact_id=data["artifact_id"],
            version_number=data["version_number"],
            file_path=data["file_path"],
            file_type=data["file_type"],
            title=data["title"],
            description=data.get("description", ""),
            parent_version=data.get("parent_version"),
            metadata=data.get("metadata", {}),
        )
        rec.created_at = data.get("created_at", rec.created_at)
        return rec


class VersionManager:
    """
    Manages versioned artifacts (DOCX/PPTX files).
    Stores version manifests as JSON files in the versions directory.
    """

    def __init__(self, versions_dir: Optional[str] = None):
        self.versions_dir = Path(versions_dir or settings.versions_dir)
        self.versions_dir.mkdir(parents=True, exist_ok=True)

    def _manifest_path(self, artifact_id: str) -> Path:
        return self.versions_dir / f"{artifact_id}.json"

    def _load_manifest(self, artifact_id: str) -> list[VersionRecord]:
        path = self._manifest_path(artifact_id)
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [VersionRecord.from_dict(r) for r in data.get("versions", [])]

    def _save_manifest(self, artifact_id: str, records: list[VersionRecord]):
        path = self._manifest_path(artifact_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"artifact_id": artifact_id, "versions": [r.to_dict() for r in records]}, f, indent=2)

    def create_artifact(self, title: str, file_type: str) -> str:
        """Create a new artifact ID for tracking versions."""
        artifact_id = str(uuid.uuid4())
        self._save_manifest(artifact_id, [])
        logger.info(f"New artifact created: {artifact_id} ({title})")
        return artifact_id

    def save_version(
        self,
        artifact_id: str,
        source_file_path: str,
        title: str,
        file_type: str,
        description: str = "",
        metadata: Optional[dict] = None,
    ) -> VersionRecord:
        """
        Save a new version of an artifact.
        Copies the file to the versions directory with a versioned filename.

        Args:
            artifact_id: The artifact's unique ID.
            source_file_path: Path to the newly generated file.
            title: Human-readable title.
            file_type: "docx" or "pptx"
            description: Description of changes.
            metadata: Additional metadata dict.

        Returns:
            The created VersionRecord.
        """
        records = self._load_manifest(artifact_id)
        version_number = len(records) + 1
        parent_version = records[-1].version_number if records else None

        # Copy file to versioned storage
        src = Path(source_file_path)
        ext = src.suffix
        versioned_filename = f"{artifact_id}_v{version_number}{ext}"
        dest = self.versions_dir / versioned_filename
        shutil.copy2(str(src), str(dest))

        record = VersionRecord(
            artifact_id=artifact_id,
            version_number=version_number,
            file_path=str(dest),
            file_type=file_type,
            title=title,
            description=description,
            parent_version=parent_version,
            metadata=metadata or {},
        )
        records.append(record)
        self._save_manifest(artifact_id, records)

        logger.info(f"Version {version_number} saved for artifact {artifact_id}: {dest}")
        return record

    def get_versions(self, artifact_id: str) -> list[dict]:
        """Return all version records for an artifact as dicts."""
        return [r.to_dict() for r in self._load_manifest(artifact_id)]

    def get_latest(self, artifact_id: str) -> Optional[VersionRecord]:
        """Return the most recent version record."""
        records = self._load_manifest(artifact_id)
        return records[-1] if records else None

    def get_version(self, artifact_id: str, version_number: int) -> Optional[VersionRecord]:
        """Return a specific version by number."""
        records = self._load_manifest(artifact_id)
        for r in records:
            if r.version_number == version_number:
                return r
        return None

    def list_artifacts(self) -> list[dict]:
        """List all tracked artifacts with their latest version info."""
        artifacts = []
        for manifest_file in self.versions_dir.glob("*.json"):
            artifact_id = manifest_file.stem
            records = self._load_manifest(artifact_id)
            if records:
                latest = records[-1]
                artifacts.append({
                    "artifact_id": artifact_id,
                    "title": latest.title,
                    "file_type": latest.file_type,
                    "version_count": len(records),
                    "latest_version": latest.version_number,
                    "latest_created_at": latest.created_at,
                })
        return sorted(artifacts, key=lambda x: x["latest_created_at"], reverse=True)

    def delete_artifact(self, artifact_id: str):
        """Delete all versions and manifest for an artifact."""
        records = self._load_manifest(artifact_id)
        for r in records:
            try:
                Path(r.file_path).unlink(missing_ok=True)
            except Exception:
                pass
        manifest = self._manifest_path(artifact_id)
        manifest.unlink(missing_ok=True)
        logger.info(f"Artifact {artifact_id} deleted ({len(records)} versions removed)")


# Singleton
_version_manager: Optional[VersionManager] = None


def get_version_manager() -> VersionManager:
    global _version_manager
    if _version_manager is None:
        _version_manager = VersionManager()
    return _version_manager
