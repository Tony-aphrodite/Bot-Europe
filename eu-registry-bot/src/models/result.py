"""
Submission result models
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class SubmissionStatus(Enum):
    """Submission status enumeration."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REJECTED = "rejected"


@dataclass
class SubmissionResult:
    """Result of a submission attempt."""

    # Status
    status: SubmissionStatus

    # Identification
    application_id: Optional[str] = None
    reference_number: Optional[str] = None  # CSV/Receipt number
    registry_number: Optional[str] = None  # Official registry number

    # Timestamps
    submitted_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None

    # Portal information
    portal: str = ""
    country: str = ""

    # Receipt/Confirmation
    receipt_path: Optional[str] = None
    confirmation_url: Optional[str] = None

    # Error information
    error_message: Optional[str] = None
    error_details: Optional[str] = None

    # Logs and screenshots
    screenshots: List[str] = field(default_factory=list)
    log_entries: List[str] = field(default_factory=list)

    def is_successful(self) -> bool:
        """Check if submission was successful."""
        return self.status in [SubmissionStatus.SUBMITTED, SubmissionStatus.CONFIRMED]

    def add_log(self, message: str) -> None:
        """Add a log entry."""
        timestamp = datetime.now().isoformat()
        self.log_entries.append(f"[{timestamp}] {message}")

    def add_screenshot(self, path: str) -> None:
        """Add a screenshot path."""
        self.screenshots.append(path)

    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "status": self.status.value,
            "application_id": self.application_id,
            "reference_number": self.reference_number,
            "registry_number": self.registry_number,
            "submitted_at": (
                self.submitted_at.isoformat() if self.submitted_at else None
            ),
            "confirmed_at": (
                self.confirmed_at.isoformat() if self.confirmed_at else None
            ),
            "portal": self.portal,
            "country": self.country,
            "receipt_path": self.receipt_path,
            "confirmation_url": self.confirmation_url,
            "error_message": self.error_message,
            "error_details": self.error_details,
            "screenshots": self.screenshots,
            "log_entries": self.log_entries,
        }

    def get_summary(self) -> str:
        """Get a human-readable summary."""
        lines = [
            f"Submission Result: {self.status.value.upper()}",
            f"Country: {self.country}",
            f"Portal: {self.portal}",
        ]

        if self.reference_number:
            lines.append(f"Reference Number: {self.reference_number}")

        if self.registry_number:
            lines.append(f"Registry Number: {self.registry_number}")

        if self.submitted_at:
            lines.append(f"Submitted At: {self.submitted_at}")

        if self.error_message:
            lines.append(f"Error: {self.error_message}")

        if self.receipt_path:
            lines.append(f"Receipt: {self.receipt_path}")

        return "\n".join(lines)

    @classmethod
    def create_success(
        cls,
        reference_number: str,
        country: str,
        portal: str,
        receipt_path: Optional[str] = None,
    ) -> "SubmissionResult":
        """Create a successful submission result."""
        return cls(
            status=SubmissionStatus.SUBMITTED,
            reference_number=reference_number,
            country=country,
            portal=portal,
            receipt_path=receipt_path,
            submitted_at=datetime.now(),
        )

    @classmethod
    def create_failure(
        cls,
        error_message: str,
        country: str,
        portal: str,
        error_details: Optional[str] = None,
    ) -> "SubmissionResult":
        """Create a failed submission result."""
        return cls(
            status=SubmissionStatus.FAILED,
            error_message=error_message,
            error_details=error_details,
            country=country,
            portal=portal,
        )
