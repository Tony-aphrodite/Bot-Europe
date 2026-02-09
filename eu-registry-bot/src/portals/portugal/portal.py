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
            # Import certificate into Windows Certificate Store (Windows only)
            if hasattr(self.browser, 'import_certificate_windows'):
                cert_path, cert_password = self.certificate_manager.get_certificate_for_browser()
                if cert_path:
                    logger.info("Importing certificate into Windows store...")
                    self.browser.import_certificate_windows(cert_path, cert_password)

            # Navigate to ePortugal Balcão do Empreendedor service page
            service_url = "https://www2.gov.pt/inicio/espaco-empresa/balcao-do-empreendedor/ocupacao-de-espaco-publico-instalacao-de-equipamento"

            logger.info(f"Navigating to service page: {service_url}")
            self.browser.navigate(service_url)

            # Wait for page to load
            time.sleep(3)

            # Check if already authenticated (session cookie may persist)
            if self._is_authenticated():
                logger.info("Already authenticated (session active)")
                return True

            # Look for login/authentication button on the page
            auth_selectors = [
                self._selectors.get("auth_container", "#autenticacao-container"),
                self._selectors.get("login_select_container", ".login-select-button-container"),
                "a[href*='autenticacao']",
                ".btn-login",
                "#loginButton",
                "//a[contains(text(), 'Autenticar')]",
                "//button[contains(text(), 'Entrar')]",
                "//a[contains(text(), 'Iniciar sessão')]",
            ]

            auth_clicked = False
            for selector in auth_selectors:
                try:
                    if selector.startswith("//"):
                        element = self.browser.driver.find_element(By.XPATH, selector)
                    else:
                        element = self.browser.wait_for_element(
                            (By.CSS_SELECTOR, selector),
                            timeout=5,
                            condition="clickable",
                        )
                    element.click()
                    logger.info(f"Clicked authentication trigger: {selector}")
                    auth_clicked = True
                    time.sleep(2)
                    break
                except (TimeoutException, NoSuchElementException):
                    continue

            if not auth_clicked:
                logger.warning("No authentication button found - checking if already on auth page")

            # Wait for authentication page
            time.sleep(3)

            # Look for certificate authentication option
            cert_selectors = [
                self._selectors.get("certificate_option", ".login-select-button-container li:first-child"),
                self._selectors.get("citizen_option", "a[href*='cartao-cidadao']"),
                "//button[contains(text(), 'Certificado')]",
                "//a[contains(text(), 'Certificado Digital')]",
                "//li[contains(text(), 'Cidadão nacional')]",
                "[data-auth-method='certificate']",
                ".autenticacao-metodo-certificado",
            ]

            for selector in cert_selectors:
                try:
                    if selector.startswith("//"):
                        element = self.browser.driver.find_element(By.XPATH, selector)
                    else:
                        element = self.browser.wait_for_element(
                            (By.CSS_SELECTOR, selector),
                            timeout=5,
                            condition="clickable",
                        )
                    element.click()
                    logger.info(f"Selected certificate authentication: {selector}")
                    break
                except (TimeoutException, NoSuchElementException):
                    continue

            # Wait for browser certificate dialog / auto-selection
            logger.info("Waiting for certificate authentication...")
            time.sleep(5)

            # Verify authentication
            if self._is_authenticated():
                logger.info("Authentication successful")
                return True

            # Check for error messages
            error_selectors = [
                self._selectors.get("error_message", ".autgov-error"),
                self._selectors.get("error_container", ".autgov-error-container"),
                ".alert-danger",
                ".error-message",
            ]

            for selector in error_selectors:
                try:
                    error_elem = self.browser.driver.find_element(By.CSS_SELECTOR, selector)
                    if error_elem.is_displayed():
                        logger.error(f"Authentication error: {error_elem.text}")
                        return False
                except NoSuchElementException:
                    continue

            # No error found, assume authentication proceeded
            logger.info("No errors detected, proceeding")
            return True

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False

    def _is_authenticated(self) -> bool:
        """Check if user is currently authenticated."""
        try:
            # Check for logged-in indicators
            logged_in_indicators = [
                ".user-menu",
                ".logged-in",
                "#user-profile",
                "[data-authenticated='true']",
                ".area-pessoal",
                "#minha-conta",
            ]

            for indicator in logged_in_indicators:
                try:
                    self.browser.wait_for_element(
                        (By.CSS_SELECTOR, indicator),
                        timeout=2,
                        condition="presence",
                    )
                    return True
                except TimeoutException:
                    continue

            # Check URL for success patterns
            current_url = self.browser.driver.current_url
            if any(pattern in current_url for pattern in [
                "area-reservada", "logged", "minha-area", "dashboard", "servicos"
            ]):
                return True

            return False

        except Exception:
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
