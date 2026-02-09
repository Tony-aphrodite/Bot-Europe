"""
Base portal class for all country implementations
"""

from abc import ABC, abstractmethod
from typing import Optional, Callable
from datetime import datetime

import yaml

from ..core.browser import BrowserManager
from ..core.certificate import CertificateManager
from ..core.logger import setup_logger
from ..models.application import Application
from ..models.result import SubmissionResult, SubmissionStatus
from ..utils.captcha import CaptchaHandler, CaptchaDetector
from ..utils.retry import RetryExecutor, RetryStrategy, CircuitBreaker
from ..utils.state import StateManager, SubmissionState, SubmissionStep

logger = setup_logger(__name__)


class BasePortal(ABC):
    """
    Abstract base class for all country portal implementations.
    """

    def __init__(
        self,
        config_path: str,
        certificate_manager: CertificateManager,
        headless: bool = True,
        state_dir: str = "./data/state",
        max_retries: int = 3,
        disable_circuit_breaker: bool = False,
    ):
        """
        Initialize portal.

        Args:
            config_path: Path to portal configuration YAML
            certificate_manager: Certificate manager instance
            headless: Run browser in headless mode
            state_dir: Directory for state persistence
            max_retries: Maximum retry attempts for operations
            disable_circuit_breaker: Disable circuit breaker for batch processing
        """
        self.config = self._load_config(config_path)
        self.certificate_manager = certificate_manager
        self.headless = headless
        self.browser: Optional[BrowserManager] = None
        self.disable_circuit_breaker = disable_circuit_breaker

        # State management
        self.state_manager = StateManager(state_dir)
        self.current_state: Optional[SubmissionState] = None

        # Retry configuration
        self.retry_executor = RetryExecutor(
            max_attempts=max_retries,
            base_delay=2.0,
            strategy=RetryStrategy.EXPONENTIAL,
        )

        # Circuit breaker for repeated failures (high threshold for batch)
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=1000 if disable_circuit_breaker else 5,
            recovery_timeout=60.0,  # 1 minute recovery
        )

        # CAPTCHA handling (initialized with browser)
        self.captcha_handler: Optional[CaptchaHandler] = None

        # Notification callback for UI
        self._notification_callback: Optional[Callable[[str], None]] = None

    def _load_config(self, config_path: str) -> dict:
        """Load portal configuration from YAML file."""
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @property
    @abstractmethod
    def country(self) -> str:
        """Return country identifier."""
        pass

    @property
    @abstractmethod
    def portal_name(self) -> str:
        """Return portal name."""
        pass

    @abstractmethod
    def authenticate(self) -> bool:
        """
        Authenticate with the portal using certificate.

        Returns:
            True if authentication successful
        """
        pass

    @abstractmethod
    def fill_form(self, application: Application) -> bool:
        """
        Fill the application form.

        Args:
            application: Application data

        Returns:
            True if form filled successfully
        """
        pass

    @abstractmethod
    def upload_attachments(self, application: Application) -> bool:
        """
        Upload required attachments.

        Args:
            application: Application with attachments

        Returns:
            True if all attachments uploaded successfully
        """
        pass

    @abstractmethod
    def submit(self) -> SubmissionResult:
        """
        Submit the application.

        Returns:
            SubmissionResult with status and reference number
        """
        pass

    @abstractmethod
    def download_receipt(self, result: SubmissionResult) -> Optional[str]:
        """
        Download submission receipt.

        Args:
            result: Submission result

        Returns:
            Path to downloaded receipt or None
        """
        pass

    def set_notification_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for status notifications."""
        self._notification_callback = callback

    def _notify(self, message: str) -> None:
        """Send notification via callback."""
        if self._notification_callback:
            self._notification_callback(message)

    def _check_captcha(self) -> bool:
        """
        Check for CAPTCHA and handle if present.

        Returns:
            True if no CAPTCHA or CAPTCHA was solved
        """
        if self.captcha_handler:
            return self.captcha_handler.check_and_handle()
        return True

    def process_application(
        self,
        application: Application,
        resume_state: Optional[SubmissionState] = None,
    ) -> SubmissionResult:
        """
        Process complete application workflow with state persistence and recovery.

        Args:
            application: Application to process
            resume_state: Optional state to resume from

        Returns:
            SubmissionResult
        """
        result = SubmissionResult(
            status=SubmissionStatus.IN_PROGRESS,
            country=self.country,
            portal=self.portal_name,
        )

        # Check circuit breaker (skip if disabled for batch processing)
        if not self.disable_circuit_breaker and self.circuit_breaker.is_open:
            result.status = SubmissionStatus.FAILED
            result.error_message = "Service temporarily unavailable (circuit breaker open)"
            return result

        try:
            # Initialize or resume state
            if resume_state:
                self.current_state = resume_state
                logger.info(f"Resuming from state: {resume_state.current_step.value}")
            else:
                self.current_state = self.state_manager.create_state(
                    application_id=application.application_id or "unknown",
                    country=self.country,
                    portal=self.portal_name,
                )

            # Validate application
            is_valid, errors = application.validate()
            if not is_valid:
                result.status = SubmissionStatus.FAILED
                result.error_message = "Validation failed"
                result.error_details = "; ".join(errors)
                self.state_manager.mark_failed(
                    self.current_state, result.error_message, result.error_details
                )
                return result

            result.add_log("Application validated successfully")
            self._notify("Application validated")

            # Initialize browser
            cert_path, _ = self.certificate_manager.get_certificate_for_browser()
            self.browser = BrowserManager(
                headless=self.headless,
                certificate_path=cert_path,
            )

            with self.browser:
                # Initialize CAPTCHA handler
                self.captcha_handler = CaptchaHandler(
                    driver=self.browser.driver,
                    auto_wait=True,
                    wait_timeout=300,
                )
                self.captcha_handler.set_notification_callback(self._notify)

                # Determine starting step
                start_step = SubmissionStep.INITIALIZED
                if resume_state:
                    recoverable = self.state_manager.get_recoverable_step(resume_state)
                    if recoverable:
                        start_step = recoverable

                # Step 1: Authenticate (with retry)
                if start_step.value <= SubmissionStep.INITIALIZED.value:
                    result.add_log("Starting authentication...")
                    self._notify("Authenticating...")

                    try:
                        auth_success = self.retry_executor.execute(self.authenticate)
                    except Exception as e:
                        auth_success = False
                        logger.error(f"Authentication failed after retries: {e}")

                    if not auth_success:
                        result.status = SubmissionStatus.FAILED
                        result.error_message = "Authentication failed"
                        self._capture_error_screenshot(result, "auth_failed")
                        self.state_manager.mark_failed(
                            self.current_state, result.error_message
                        )
                        self.circuit_breaker.record_failure()
                        return result

                    # Check for CAPTCHA after auth
                    if not self._check_captcha():
                        result.status = SubmissionStatus.FAILED
                        result.error_message = "CAPTCHA not solved"
                        self._capture_error_screenshot(result, "captcha_timeout")
                        self.state_manager.mark_failed(
                            self.current_state, result.error_message
                        )
                        return result

                    self.state_manager.update_step(
                        self.current_state, SubmissionStep.AUTHENTICATED
                    )
                    result.add_log("Authentication successful")
                    self._notify("Authentication successful")

                # Step 2: Fill form (with retry)
                if start_step.value <= SubmissionStep.AUTHENTICATED.value:
                    result.add_log("Filling application form...")
                    self._notify("Filling form...")

                    try:
                        form_success = self.retry_executor.execute(
                            self.fill_form, application
                        )
                    except Exception as e:
                        form_success = False
                        logger.error(f"Form filling failed after retries: {e}")

                    if not form_success:
                        result.status = SubmissionStatus.FAILED
                        result.error_message = "Form filling failed"
                        self._capture_error_screenshot(result, "form_failed")
                        self.state_manager.mark_failed(
                            self.current_state, result.error_message
                        )
                        return result

                    self.state_manager.update_step(
                        self.current_state, SubmissionStep.FORM_FILLED
                    )
                    result.add_log("Form filled successfully")
                    self._notify("Form filled")

                # Step 3: Upload attachments
                if start_step.value <= SubmissionStep.FORM_FILLED.value:
                    result.add_log("Uploading attachments...")
                    self._notify("Uploading attachments...")

                    try:
                        upload_success = self.retry_executor.execute(
                            self.upload_attachments, application
                        )
                    except Exception as e:
                        upload_success = False
                        logger.error(f"Attachment upload failed after retries: {e}")

                    if not upload_success:
                        result.status = SubmissionStatus.FAILED
                        result.error_message = "Attachment upload failed"
                        self._capture_error_screenshot(result, "upload_failed")
                        self.state_manager.mark_failed(
                            self.current_state, result.error_message
                        )
                        return result

                    self.state_manager.update_step(
                        self.current_state, SubmissionStep.ATTACHMENTS_UPLOADED
                    )
                    result.add_log("Attachments uploaded successfully")
                    self._notify("Attachments uploaded")

                # Step 4: Submit (NO retry - one attempt only to avoid duplicates)
                if start_step.value <= SubmissionStep.ATTACHMENTS_UPLOADED.value:
                    result.add_log("Submitting application...")
                    self._notify("Submitting application...")

                    # Check for CAPTCHA before submission
                    if not self._check_captcha():
                        result.status = SubmissionStatus.FAILED
                        result.error_message = "CAPTCHA not solved before submission"
                        self._capture_error_screenshot(result, "captcha_submit")
                        self.state_manager.mark_failed(
                            self.current_state, result.error_message
                        )
                        return result

                    submit_result = self.submit()

                    if submit_result.is_successful():
                        self.state_manager.update_step(
                            self.current_state,
                            SubmissionStep.SUBMITTED,
                            reference_number=submit_result.reference_number,
                        )

                        result.status = submit_result.status
                        result.reference_number = submit_result.reference_number
                        result.registry_number = submit_result.registry_number
                        result.submitted_at = submit_result.submitted_at
                        result.add_log(
                            f"Submission successful. Reference: {result.reference_number}"
                        )
                        self._notify(f"Submitted! Reference: {result.reference_number}")

                        # Step 5: Download receipt
                        receipt_path = self.download_receipt(result)
                        if receipt_path:
                            result.receipt_path = receipt_path
                            result.add_log(f"Receipt downloaded: {receipt_path}")
                            self.state_manager.update_step(
                                self.current_state,
                                SubmissionStep.RECEIPT_DOWNLOADED,
                                receipt_path=receipt_path,
                            )

                        # Mark completed
                        self.state_manager.update_step(
                            self.current_state, SubmissionStep.COMPLETED
                        )
                        self.circuit_breaker.record_success()

                    else:
                        result.status = SubmissionStatus.FAILED
                        result.error_message = submit_result.error_message
                        result.error_details = submit_result.error_details
                        self._capture_error_screenshot(result, "submit_failed")
                        self.state_manager.mark_failed(
                            self.current_state,
                            submit_result.error_message,
                            submit_result.error_details,
                        )
                        self.circuit_breaker.record_failure()

        except Exception as e:
            logger.error(f"Error processing application: {e}")
            result.status = SubmissionStatus.FAILED
            result.error_message = str(e)
            self._capture_error_screenshot(result, "exception")
            if self.current_state:
                self.state_manager.mark_failed(self.current_state, str(e))
            self.circuit_breaker.record_failure()

        return result

    def _capture_error_screenshot(self, result: SubmissionResult, name: str) -> None:
        """Capture screenshot on error and save to state."""
        if self.browser and self.browser.driver:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{self.country}_{name}_{timestamp}.png"
                path = self.browser.take_screenshot(filename)
                result.add_screenshot(path)

                # Also save to state for recovery reference
                if self.current_state:
                    self.state_manager.add_screenshot(self.current_state, path)

                logger.info(f"Error screenshot captured: {path}")
            except Exception as e:
                logger.error(f"Failed to capture screenshot: {e}")

    def get_incomplete_submissions(self) -> list:
        """
        Get all incomplete submissions that can be recovered.

        Returns:
            List of recoverable submission states
        """
        return self.state_manager.get_incomplete_submissions()

    def resume_submission(
        self,
        submission_id: str,
        application: Application,
    ) -> SubmissionResult:
        """
        Resume an incomplete submission.

        Args:
            submission_id: ID of submission to resume
            application: Application data

        Returns:
            SubmissionResult
        """
        state = self.state_manager.load_state(submission_id)
        if not state:
            return SubmissionResult.create_failure(
                error_message=f"State not found: {submission_id}",
                country=self.country,
                portal=self.portal_name,
            )

        recoverable = self.state_manager.get_recoverable_step(state)
        if not recoverable:
            return SubmissionResult.create_failure(
                error_message="Submission cannot be recovered from current state",
                country=self.country,
                portal=self.portal_name,
            )

        logger.info(f"Resuming submission {submission_id} from {recoverable.value}")
        return self.process_application(application, resume_state=state)
