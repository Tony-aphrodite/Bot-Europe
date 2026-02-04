"""
Data models for EU Registry Bot
"""

from .application import Application, Applicant, InstallationDetails
from .result import SubmissionResult, SubmissionStatus

__all__ = [
    "Application",
    "Applicant",
    "InstallationDetails",
    "SubmissionResult",
    "SubmissionStatus",
]
