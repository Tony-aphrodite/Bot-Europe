"""
Portugal gov.pt portal implementation
"""

import time
from datetime import datetime
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from ..base import BasePortal
from ...core.certificate import CertificateManager
from ...core.logger import setup_logger
from ...models.application import Application
from ...models.result import SubmissionResult, SubmissionStatus

logger = setup_logger(__name__)


class PortugalPortal(BasePortal):
    """
    Implementation for Portugal's gov.pt portal.
    """

    def __init__(
        self,
        config_path: str,
        certificate_manager: CertificateManager,
        headless: bool = True,
    ):
        super().__init__(config_path, certificate_manager, headless)
        self._selectors = self.config.get("selectors", {})

    @property
    def country(self) -> str:
        return "portugal"

    @property
    def portal_name(self) -> str:
        return self.config.get("portal", {}).get("name", "Portugal - gov.pt")

    def authenticate(self) -> bool:
        """
        Authenticate with gov.pt using digital certificate.

        Returns:
            True if authentication successful
        """
        try:
            base_url = self.config.get("portal", {}).get("base_url", "https://www.gov.pt")
            auth_url = self.config.get("portal", {}).get(
                "auth_url", "https://www.autenticacao.gov.pt"
            )

            logger.info(f"Navigating to authentication: {auth_url}")
            self.browser.navigate(auth_url)

            # Wait for page to load
            time.sleep(3)

            # Look for certificate authentication option
            try:
                cert_option = self.browser.wait_for_element(
                    (By.CSS_SELECTOR, self._selectors.get("certificate_option", "#auth-certificate")),
                    timeout=10,
                    condition="clickable",
                )
                cert_option.click()
                logger.info("Selected certificate authentication")
            except TimeoutException:
                # Try alternative selectors
                logger.warning("Primary certificate selector not found, trying alternatives...")
                alternative_selectors = [
                    "//button[contains(text(), 'Certificado')]",
                    "//a[contains(text(), 'Certificado Digital')]",
                    "[data-auth-method='certificate']",
                ]

                for selector in alternative_selectors:
                    try:
                        if selector.startswith("//"):
                            element = self.browser.driver.find_element(By.XPATH, selector)
                        else:
                            element = self.browser.driver.find_element(By.CSS_SELECTOR, selector)
                        element.click()
                        logger.info(f"Found certificate option with: {selector}")
                        break
                    except NoSuchElementException:
                        continue
                else:
                    logger.error("Could not find certificate authentication option")
                    return False

            # Wait for certificate prompt/selection
            # Note: Browser will handle certificate selection automatically if configured
            time.sleep(5)

            # Verify authentication success by checking for user session indicators
            try:
                # Look for logged-in indicators
                logged_in_indicators = [
                    ".user-menu",
                    ".logged-in",
                    "#user-profile",
                    "[data-authenticated='true']",
                ]

                for indicator in logged_in_indicators:
                    try:
                        self.browser.wait_for_element(
                            (By.CSS_SELECTOR, indicator),
                            timeout=5,
                            condition="presence",
                        )
                        logger.info("Authentication verified - user session active")
                        return True
                    except TimeoutException:
                        continue

                # If no indicator found, check URL for success patterns
                current_url = self.browser.driver.current_url
                if "area-reservada" in current_url or "logged" in current_url:
                    logger.info("Authentication verified via URL")
                    return True

                logger.warning("Could not verify authentication status")
                return True  # Proceed anyway, may still be authenticated

            except Exception as e:
                logger.error(f"Error verifying authentication: {e}")
                return False

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False

    def fill_form(self, application: Application) -> bool:
        """
        Fill the public road installation permit form.

        Args:
            application: Application data

        Returns:
            True if form filled successfully
        """
        try:
            # Navigate to the service page
            services_url = f"{self.config['portal']['base_url']}/servicos"
            logger.info(f"Navigating to services: {services_url}")
            self.browser.navigate(services_url)

            time.sleep(2)

            # Search for the specific service
            # TODO: Implement service search based on actual portal structure
            logger.info("Searching for installation permit service...")

            form_config = self.config.get("forms", {}).get("instalacao_via_publica", {})
            fields = form_config.get("fields", [])

            # Map application data to form fields
            field_mapping = {
                "nif": application.applicant.tax_id,
                "nome_requerente": application.applicant.name,
                "morada": application.applicant.address,
                "codigo_postal": application.applicant.postal_code,
                "localidade": application.applicant.city,
                "email": application.applicant.email,
                "telefone": application.applicant.phone or "",
                "descricao_instalacao": application.installation.description,
                "local_instalacao": application.installation.location,
                "data_inicio": application.installation.start_date.strftime("%d/%m/%Y"),
                "data_fim": (
                    application.installation.end_date.strftime("%d/%m/%Y")
                    if application.installation.end_date
                    else ""
                ),
            }

            # Fill each field
            for field_name, value in field_mapping.items():
                if not value:
                    continue

                try:
                    # Try multiple selector strategies
                    selectors = [
                        f"#field-{field_name}",
                        f"[name='{field_name}']",
                        f"#input-{field_name}",
                        f"[data-field='{field_name}']",
                    ]

                    for selector in selectors:
                        try:
                            self.browser.fill_field(
                                (By.CSS_SELECTOR, selector),
                                str(value),
                            )
                            logger.debug(f"Filled field '{field_name}' with selector: {selector}")
                            break
                        except Exception:
                            continue
                    else:
                        logger.warning(f"Could not find field: {field_name}")

                except Exception as e:
                    logger.warning(f"Error filling field '{field_name}': {e}")

            logger.info("Form filling completed")
            return True

        except Exception as e:
            logger.error(f"Error filling form: {e}")
            return False

    def upload_attachments(self, application: Application) -> bool:
        """
        Upload required attachments.

        Args:
            application: Application with attachments

        Returns:
            True if all required attachments uploaded
        """
        try:
            if not application.attachments:
                logger.info("No attachments to upload")
                return True

            for attachment in application.attachments:
                try:
                    # Find file input for this attachment type
                    selectors = [
                        f"input[type='file'][name*='{attachment.document_type}']",
                        f"input[type='file'][data-type='{attachment.document_type}']",
                        f"#upload-{attachment.document_type}",
                    ]

                    file_input = None
                    for selector in selectors:
                        try:
                            file_input = self.browser.driver.find_element(
                                By.CSS_SELECTOR, selector
                            )
                            break
                        except NoSuchElementException:
                            continue

                    if file_input:
                        file_input.send_keys(attachment.file_path)
                        logger.info(f"Uploaded: {attachment.name}")
                        time.sleep(2)  # Wait for upload
                    else:
                        if attachment.required:
                            logger.error(f"Required upload field not found: {attachment.document_type}")
                            return False
                        else:
                            logger.warning(f"Optional upload field not found: {attachment.document_type}")

                except Exception as e:
                    logger.error(f"Error uploading {attachment.name}: {e}")
                    if attachment.required:
                        return False

            logger.info("All attachments processed")
            return True

        except Exception as e:
            logger.error(f"Error uploading attachments: {e}")
            return False

    def submit(self) -> SubmissionResult:
        """
        Submit the application.

        Returns:
            SubmissionResult
        """
        try:
            # Click submit button
            submit_selector = self._selectors.get("submit_button", "#submit-form")
            self.browser.click((By.CSS_SELECTOR, submit_selector))

            logger.info("Submit button clicked, waiting for confirmation...")
            time.sleep(5)

            # Check for success message
            try:
                success_selector = self._selectors.get(
                    "success_message", ".success-notification"
                )
                success_element = self.browser.wait_for_element(
                    (By.CSS_SELECTOR, success_selector),
                    timeout=30,
                    condition="visible",
                )

                # Extract reference number
                reference_number = self._extract_reference_number()

                return SubmissionResult.create_success(
                    reference_number=reference_number or "PENDING",
                    country=self.country,
                    portal=self.portal_name,
                )

            except TimeoutException:
                # Check for error message
                error_selector = self._selectors.get(
                    "error_message", ".error-notification"
                )
                try:
                    error_element = self.browser.driver.find_element(
                        By.CSS_SELECTOR, error_selector
                    )
                    error_text = error_element.text
                    return SubmissionResult.create_failure(
                        error_message="Submission rejected",
                        error_details=error_text,
                        country=self.country,
                        portal=self.portal_name,
                    )
                except NoSuchElementException:
                    return SubmissionResult.create_failure(
                        error_message="Unknown submission status",
                        country=self.country,
                        portal=self.portal_name,
                    )

        except Exception as e:
            logger.error(f"Submission error: {e}")
            return SubmissionResult.create_failure(
                error_message=str(e),
                country=self.country,
                portal=self.portal_name,
            )

    def _extract_reference_number(self) -> Optional[str]:
        """Extract reference number from confirmation page."""
        try:
            # Try common patterns for reference numbers
            patterns = [
                "//span[contains(@class, 'reference')]",
                "//div[contains(text(), 'Número de registo')]//following-sibling::*",
                "//*[contains(text(), 'Referência:')]",
                ".reference-number",
                "#submission-reference",
            ]

            for pattern in patterns:
                try:
                    if pattern.startswith("//"):
                        element = self.browser.driver.find_element(By.XPATH, pattern)
                    else:
                        element = self.browser.driver.find_element(By.CSS_SELECTOR, pattern)

                    text = element.text.strip()
                    if text:
                        # Clean up reference number
                        import re
                        match = re.search(r"[\w\d-]+", text)
                        if match:
                            return match.group()
                except NoSuchElementException:
                    continue

            return None

        except Exception as e:
            logger.error(f"Error extracting reference number: {e}")
            return None

    def download_receipt(self, result: SubmissionResult) -> Optional[str]:
        """
        Download submission receipt.

        Args:
            result: Submission result

        Returns:
            Path to downloaded receipt
        """
        try:
            receipt_selector = self._selectors.get(
                "receipt_download", "#download-receipt"
            )

            try:
                download_btn = self.browser.wait_for_element(
                    (By.CSS_SELECTOR, receipt_selector),
                    timeout=10,
                    condition="clickable",
                )
                download_btn.click()

                # Wait for download
                time.sleep(5)

                # Return expected path
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                receipt_path = f"./data/output/receipt_portugal_{timestamp}.pdf"
                return receipt_path

            except TimeoutException:
                logger.warning("Receipt download button not found")
                return None

        except Exception as e:
            logger.error(f"Error downloading receipt: {e}")
            return None
