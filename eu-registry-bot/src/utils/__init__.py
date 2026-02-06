"""
Utility modules for EU Registry Bot
"""

from .file_handler import FileHandler
from .captcha import CaptchaDetector, CaptchaHandler, CaptchaType, CaptchaDetectionResult
from .retry import (
    retry,
    RetryExecutor,
    RetryStrategy,
    CircuitBreaker,
    RETRYABLE_EXCEPTIONS,
)
from .state import StateManager, SubmissionState, SubmissionStep

# Excel support (optional - requires openpyxl)
try:
    from .excel_reader import (
        ExcelReader,
        BatchProcessor,
        MunicipalityRecord,
        ExcelBatchResult,
        ExcelColumnMapping,
    )
    EXCEL_SUPPORT = True
except ImportError:
    EXCEL_SUPPORT = False
    ExcelReader = None
    BatchProcessor = None
    MunicipalityRecord = None
    ExcelBatchResult = None
    ExcelColumnMapping = None

__all__ = [
    "FileHandler",
    "CaptchaDetector",
    "CaptchaHandler",
    "CaptchaType",
    "CaptchaDetectionResult",
    "retry",
    "RetryExecutor",
    "RetryStrategy",
    "CircuitBreaker",
    "RETRYABLE_EXCEPTIONS",
    "StateManager",
    "SubmissionState",
    "SubmissionStep",
    "EXCEL_SUPPORT",
    "ExcelReader",
    "BatchProcessor",
    "MunicipalityRecord",
    "ExcelBatchResult",
    "ExcelColumnMapping",
]
