"""Custom exceptions for the storage advisor."""


class StorageAdvisorError(Exception):
    """Base exception for all storage advisor errors."""


class ScenarioValidationError(StorageAdvisorError):
    """Raised when scenario input fails validation."""


class ConfigurationError(StorageAdvisorError):
    """Raised when knowledge base or rule configuration is invalid."""


class RecommendationError(StorageAdvisorError):
    """Raised when the recommendation pipeline fails."""
