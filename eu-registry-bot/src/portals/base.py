"""
Base portal class for all country implementations
"""

from abc import ABC, abstractmethod
from typing import Optional

import yaml

from ..core.browser import BrowserManager
from ..core.certificate import CertificateManager
from ..core.logger import setup_logger
from ..models.application import Application
from ..models.result import SubmissionResult, SubmissionStatus

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
    ):
        """
        Initialize portal.

        Args:
            config_path: Path to portal configuration YAML
            certificate_manager: Certificate manager instance
            headless: Run browser in headless mode
        """
        self.config = self._load_config(config_path)
        self.certificate_manager = certificate_manager
        self.headless = headless
        self.browser: Optional[BrowserManager] = None

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

    def process_application(self, application: Application) -> SubmissionResult:
        """
        Process complete application workflow.

        Args:
            application: Application to process

        Returns:
            SubmissionResult
        """
        result = SubmissionResult(
            status=SubmissionStatus.IN_PROGRESS,
            country=self.country,
            portal=self.portal_name,
        )

        try:
            # Validate application
            is_valid, errors = application.validate()
            if not is_valid:
                result.status = SubmissionStatus.FAILED
                result.error_message = "Validation failed"
                result.error_details = "; ".join(errors)
                return result

            result.add_log("Application validated successfully")

            # Initialize browser
            cert_path, _ = self.certificate_manager.get_certificate_for_browser()
            self.browser = BrowserManager(
                headless=self.headless,
                certificate_path=cert_path,
            )

            with self.browser:
                # Step 1: Authenticate
                result.add_log("Starting authentication...")
                if not self.authenticate():
                    result.status = SubmissionStatus.FAILED
                    result.error_message = "Authentication failed"
                    self._capture_error_screenshot(result, "auth_failed")
                    return result

                result.add_log("Authentication successful")

                # Step 2: Fill form
                result.add_log("Filling application form...")
                if not self.fill_form(application):
                    result.status = SubmissionStatus.FAILED
                    result.error_message = "Form filling failed"
                    self._capture_error_screenshot(result, "form_failed")
                    return result

                result.add_log("Form filled successfully")

                # Step 3: Upload attachments
                result.add_log("Uploading attachments...")
                if not self.upload_attachments(application):
                    result.status = SubmissionStatus.FAILED
                    result.error_message = "Attachment upload failed"
                    self._capture_error_screenshot(result, "upload_failed")
                    return result

                result.add_log("Attachments uploaded successfully")

                # Step 4: Submit
                result.add_log("Submitting application...")
                submit_result = self.submit()

                if submit_result.is_successful():
                    result.status = submit_result.status
                    result.reference_number = submit_result.reference_number
                    result.registry_number = submit_result.registry_number
                    result.submitted_at = submit_result.submitted_at
                    result.add_log(
                        f"Submission successful. Reference: {result.reference_number}"
                    )

                    # Step 5: Download receipt
                    receipt_path = self.download_receipt(result)
                    if receipt_path:
                        result.receipt_path = receipt_path
                        result.add_log(f"Receipt downloaded: {receipt_path}")
                else:
                    result.status = SubmissionStatus.FAILED
                    result.error_message = submit_result.error_message
                    result.error_details = submit_result.error_details
                    self._capture_error_screenshot(result, "submit_failed")

        except Exception as e:
            logger.error(f"Error processing application: {e}")
            result.status = SubmissionStatus.FAILED
            result.error_message = str(e)
            self._capture_error_screenshot(result, "exception")

        return result

    def _capture_error_screenshot(self, result: SubmissionResult, name: str) -> None:
        """Capture screenshot on error."""
        if self.browser and self.browser.driver:
            try:
                from datetime import datetime

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{self.country}_{name}_{timestamp}.png"
                path = self.browser.take_screenshot(filename)
                result.add_screenshot(path)
            except Exception as e:
                logger.error(f"Failed to capture screenshot: {e}")
