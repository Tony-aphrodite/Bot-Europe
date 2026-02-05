"""
State persistence for submission recovery
"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass, asdict
import hashlib

from ..core.logger import setup_logger

logger = setup_logger(__name__)


class SubmissionStep(Enum):
    """Submission workflow steps."""
    INITIALIZED = "initialized"
    AUTHENTICATED = "authenticated"
    FORM_FILLED = "form_filled"
    ATTACHMENTS_UPLOADED = "attachments_uploaded"
    SUBMITTED = "submitted"
    RECEIPT_DOWNLOADED = "receipt_downloaded"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SubmissionState:
    """State of a submission process."""
    submission_id: str
    application_id: str
    country: str
    portal: str
    current_step: SubmissionStep
    started_at: str
    updated_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    error_details: Optional[str] = None
    reference_number: Optional[str] = None
    receipt_path: Optional[str] = None
    screenshots: List[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.screenshots is None:
            self.screenshots = []
        if self.metadata is None:
            self.metadata = {}


class StateManager:
    """
    Manages submission state persistence for recovery.
    """

    def __init__(self, state_dir: str = "./data/state"):
        """
        Initialize state manager.

        Args:
            state_dir: Directory for state files
        """
        self.state_dir = state_dir
        os.makedirs(state_dir, exist_ok=True)

    def _get_state_path(self, submission_id: str) -> str:
        """Get path to state file."""
        return os.path.join(self.state_dir, f"{submission_id}.json")

    def _generate_submission_id(self, application_id: str, country: str) -> str:
        """Generate unique submission ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        hash_input = f"{application_id}_{country}_{timestamp}"
        short_hash = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        return f"{country}_{timestamp}_{short_hash}"

    def create_state(
        self,
        application_id: str,
        country: str,
        portal: str,
    ) -> SubmissionState:
        """
        Create new submission state.

        Args:
            application_id: Application identifier
            country: Country code
            portal: Portal name

        Returns:
            New SubmissionState
        """
        now = datetime.now().isoformat()
        submission_id = self._generate_submission_id(application_id, country)

        state = SubmissionState(
            submission_id=submission_id,
            application_id=application_id,
            country=country,
            portal=portal,
            current_step=SubmissionStep.INITIALIZED,
            started_at=now,
            updated_at=now,
        )

        self.save_state(state)
        logger.info(f"Created submission state: {submission_id}")

        return state

    def save_state(self, state: SubmissionState) -> bool:
        """
        Save submission state to file.

        Args:
            state: State to save

        Returns:
            True if saved successfully
        """
        try:
            state.updated_at = datetime.now().isoformat()
            state_dict = asdict(state)
            state_dict["current_step"] = state.current_step.value

            state_path = self._get_state_path(state.submission_id)
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(state_dict, f, indent=2, ensure_ascii=False)

            logger.debug(f"Saved state: {state.submission_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            return False

    def load_state(self, submission_id: str) -> Optional[SubmissionState]:
        """
        Load submission state from file.

        Args:
            submission_id: Submission identifier

        Returns:
            SubmissionState or None if not found
        """
        state_path = self._get_state_path(submission_id)

        if not os.path.exists(state_path):
            logger.warning(f"State file not found: {submission_id}")
            return None

        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state_dict = json.load(f)

            state_dict["current_step"] = SubmissionStep(state_dict["current_step"])

            return SubmissionState(**state_dict)

        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            return None

    def update_step(
        self,
        state: SubmissionState,
        step: SubmissionStep,
        **kwargs
    ) -> SubmissionState:
        """
        Update submission step.

        Args:
            state: Current state
            step: New step
            **kwargs: Additional fields to update

        Returns:
            Updated state
        """
        state.current_step = step

        for key, value in kwargs.items():
            if hasattr(state, key):
                setattr(state, key, value)

        if step == SubmissionStep.COMPLETED:
            state.completed_at = datetime.now().isoformat()

        self.save_state(state)
        logger.info(f"Updated state {state.submission_id}: {step.value}")

        return state

    def mark_failed(
        self,
        state: SubmissionState,
        error_message: str,
        error_details: Optional[str] = None,
    ) -> SubmissionState:
        """
        Mark submission as failed.

        Args:
            state: Current state
            error_message: Error message
            error_details: Additional error details

        Returns:
            Updated state
        """
        state.current_step = SubmissionStep.FAILED
        state.error_message = error_message
        state.error_details = error_details

        self.save_state(state)
        logger.error(f"Submission failed: {state.submission_id} - {error_message}")

        return state

    def add_screenshot(self, state: SubmissionState, screenshot_path: str) -> None:
        """Add screenshot to state."""
        state.screenshots.append(screenshot_path)
        self.save_state(state)

    def get_incomplete_submissions(self) -> List[SubmissionState]:
        """
        Get all incomplete submissions for recovery.

        Returns:
            List of incomplete submission states
        """
        incomplete = []

        for filename in os.listdir(self.state_dir):
            if not filename.endswith(".json"):
                continue

            submission_id = filename[:-5]
            state = self.load_state(submission_id)

            if state and state.current_step not in (
                SubmissionStep.COMPLETED,
                SubmissionStep.FAILED,
            ):
                incomplete.append(state)

        return incomplete

    def get_recoverable_step(self, state: SubmissionState) -> Optional[SubmissionStep]:
        """
        Determine which step to resume from.

        Args:
            state: Submission state

        Returns:
            Step to resume from, or None if not recoverable
        """
        # Define recovery points (can resume from these steps)
        recovery_map = {
            SubmissionStep.INITIALIZED: SubmissionStep.INITIALIZED,
            SubmissionStep.AUTHENTICATED: SubmissionStep.AUTHENTICATED,
            SubmissionStep.FORM_FILLED: SubmissionStep.FORM_FILLED,
            SubmissionStep.ATTACHMENTS_UPLOADED: SubmissionStep.ATTACHMENTS_UPLOADED,
            # Cannot recover after submission attempt
            SubmissionStep.SUBMITTED: None,
            SubmissionStep.RECEIPT_DOWNLOADED: SubmissionStep.RECEIPT_DOWNLOADED,
            SubmissionStep.COMPLETED: None,
            SubmissionStep.FAILED: SubmissionStep.INITIALIZED,  # Restart from beginning
        }

        return recovery_map.get(state.current_step)

    def cleanup_old_states(self, days: int = 30) -> int:
        """
        Remove state files older than specified days.

        Args:
            days: Age threshold in days

        Returns:
            Number of files removed
        """
        import time

        removed = 0
        threshold = time.time() - (days * 24 * 60 * 60)

        for filename in os.listdir(self.state_dir):
            if not filename.endswith(".json"):
                continue

            filepath = os.path.join(self.state_dir, filename)
            if os.path.getmtime(filepath) < threshold:
                os.remove(filepath)
                removed += 1
                logger.info(f"Removed old state file: {filename}")

        return removed
