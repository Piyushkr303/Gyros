from __future__ import annotations

from pydantic import BaseModel, Field


class ChangedFile(BaseModel):
    filename: str
    status: str  # added / modified / removed / renamed
    additions: int = 0
    deletions: int = 0
    extension: str = ""
    is_test: bool = False


class ImpactAnalysisResult(BaseModel):
    frontend_changed: bool = False
    backend_changed: bool = False
    database_changed: bool = False
    api_changed: bool = False
    security_sensitive: bool = False
    tests_changed: bool = False
    dependency_changed: bool = False
    changed_files: list[ChangedFile] = Field(default_factory=list)
    changed_functions: list[str] = Field(default_factory=list)
    changed_imports: list[str] = Field(default_factory=list)
    reasons: dict[str, str] = Field(default_factory=dict)
