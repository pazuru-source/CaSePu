"""
Custom exception classes for CaSePu application.
Provides specific exceptions for better error handling.
"""


class CaSePuException(Exception):
    """Base exception for all CaSePu errors."""
    pass


class TickerDataError(CaSePuException):
    """Raised when ticker data cannot be fetched or is invalid."""
    pass


class OptionsChainError(CaSePuException):
    """Raised when options chain data is unavailable or invalid."""
    pass


class ConfigurationError(CaSePuException):
    """Raised when configuration is invalid."""
    pass


class ValidationError(CaSePuException):
    """Raised when user input validation fails."""
    pass


class CalculationError(CaSePuException):
    """Raised when financial calculations fail."""
    pass
