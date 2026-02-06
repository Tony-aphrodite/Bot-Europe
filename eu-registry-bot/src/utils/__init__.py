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

# Data file support (Excel, CSV, DOCX)
try:
    from .excel_reader import (
        ExcelReader,
        CSVReader,
        DocxReader,
        DataReader,
        BatchProcessor,
        MunicipalityRecord,
        ExcelBatchResult,
        ExcelColumnMapping,
    )
    EXCEL_SUPPORT = True
    DATA_READER_SUPPORT = True
except ImportError:
    EXCEL_SUPPORT = False
    DATA_READER_SUPPORT = False
    ExcelReader = None
    CSVReader = None
    DocxReader = None
    DataReader = None
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
    "DATA_READER_SUPPORT",
    "ExcelReader",
    "CSVReader",
    "DocxReader",
    "DataReader",
    "BatchProcessor",
    "MunicipalityRecord",
    "ExcelBatchResult",
    "ExcelColumnMapping",
]
