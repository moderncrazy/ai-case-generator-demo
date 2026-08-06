"""Profile Registry domain — domain profiles, drafts, versions, and migrations."""

from src.modules.profiles.models import (
    DomainProfile,
    DomainProfileDraft,
    DomainProfileVersion,
    ProfileMigration,
)
from src.modules.profiles.repository import (
    BuiltinProfileCannotBeDeleted,
    BuiltinProfileCannotBeDisabled,
    ProfileDomainError,
    ProfileNotFound,
    ProfileRepository,
    ProfileVersionAlreadyExists,
    ProfileVersionNotSequential,
)

__all__ = [
    "DomainProfile",
    "DomainProfileDraft",
    "DomainProfileVersion",
    "ProfileMigration",
    "ProfileRepository",
    "ProfileDomainError",
    "BuiltinProfileCannotBeDeleted",
    "BuiltinProfileCannotBeDisabled",
    "ProfileNotFound",
    "ProfileVersionAlreadyExists",
    "ProfileVersionNotSequential",
]
