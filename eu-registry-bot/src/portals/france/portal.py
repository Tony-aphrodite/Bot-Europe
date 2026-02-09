"""
France Service-Public.fr portal implementation
"""

import time
from datetime import datetime
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from ..base import BasePortal
from ...core.certificate import CertificateManager
from ...core.logger import setup_logger
from ...models.application import Application
from ...models.result import SubmissionResult, SubmissionStatus

logger = setup_logger(__name__)


class FrancePortal(BasePortal):
    """
    Implementation for France's Service-Public.fr portal.
    Handles Cerfa 14023*01 form for public road installation permits.
    """

    def __init__(
        self,
        config_path: str,
        certificate_manager: CertificateManager,
        headless: bool = True,
        disable_circuit_breaker: bool = False,
    ):
        super().__init__(config_path, certificate_manager, headless, disable_circuit_breaker=disable_circuit_breaker)
        self._selectors = self.config.get("selectors", {})

    @property
    def country(self) -> str:
        return "france"

    @property
    def portal_name(self) -> str:
        return self.config.get("portal", {}).get("name", "France - Service-Public.fr")

    def authenticate(self) -> bool:
        """
        Authenticate with Service-Public.fr using digital certificate.

        Returns:
            True if authentication successful
        """
        try:
            base_url = self.config.get("portal", {}).get(
                "base_url", "https://www.service-public.gouv.fr"
            )

            logger.info(f"Navigating to: {base_url}")
            self.browser.navigate(base_url)

            time.sleep(3)

            # Look for connection/login button
            try:
                login_btn = self.browser.wait_for_element(
                    (By.CSS_SELECTOR, self._selectors.get("login_button", "#se-connecter")),
                    timeout=10,
                    condition="clickable",
                )
                login_btn.click()
                logger.info("Clicked login button")
            except TimeoutException:
                # Try alternative selectors
                alternatives = [
                    "//button[contains(text(), 'Se connecter')]",
                    "//a[contains(text(), 'Connexion')]",
                    ".fr-btn--connexion",
                    "[data-action='login']",
                ]

                for selector in alternatives:
                    try:
                        if selector.startswith("//"):
                            element = self.browser.driver.find_element(By.XPATH, selector)
                        else:
                            element = self.browser.driver.find_element(By.CSS_SELECTOR, selector)
                        element.click()
                        logger.info(f"Found login with: {selector}")
                        break
                    except NoSuchElementException:
                        continue
                else:
                    logger.warning("Login button not found, may not be required")

            time.sleep(2)

            # Look for certificate authentication option
            try:
                cert_selectors = [
                    self._selectors.get("certificate_option", ".auth-certificate"),
                    "//button[contains(text(), 'Certificat')]",
                    "//a[contains(text(), 'certificat électronique')]",
                    "[data-auth='certificate']",
                ]

                for selector in cert_selectors:
                    try:
                        if selector.startswith("//"):
                            element = self.browser.driver.find_element(By.XPATH, selector)
                        else:
                            element = self.browser.driver.find_element(By.CSS_SELECTOR, selector)
                        element.click()
                        logger.info("Selected certificate authentication")
                        break
                    except NoSuchElementException:
                        continue

            except Exception as e:
                logger.warning(f"Certificate option selection: {e}")

            # Wait for certificate authentication
            time.sleep(5)

            # Verify authentication
            logged_in_indicators = [
                ".fr-header__user-logged",
                "[data-user-logged='true']",
                ".user-account",
            ]

            for indicator in logged_in_indicators:
                try:
                    self.browser.wait_for_element(
                        (By.CSS_SELECTOR, indicator),
                        timeout=5,
                        condition="presence",
                    )
                    logger.info("Authentication verified")
                    return True
                except TimeoutException:
                    continue

            # If no explicit indicator, proceed anyway
            logger.info("Proceeding with authentication (no explicit indicator)")
            return True

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False

    def fill_form(self, application: Application) -> bool:
        """
        Fill the Cerfa 14023*01 form for public road installation permit.

        Args:
            application: Application data

        Returns:
            True if form filled successfully
        """
        try:
            # Navigate to the form page
            form_url = self.config.get("forms", {}).get(
                "installation_voie_publique", {}
            ).get("url", "/vosdroits/R17000")

            enterprise_url = self.config.get("portal", {}).get(
                "enterprise_url", "https://entreprendre.service-public.gouv.fr"
            )

            full_url = f"{enterprise_url}{form_url}"
            logger.info(f"Navigating to form: {full_url}")
            self.browser.navigate(full_url)

            time.sleep(3)

            # Step 1: Select location to determine authority
            if application.installation.location:
                try:
                    location_input = self.browser.wait_for_element(
                        (By.CSS_SELECTOR, self._selectors.get("location_input", "#commune-input")),
                        timeout=10,
                        condition="visible",
                    )
                    location_input.send_keys(application.applicant.city)
                    time.sleep(2)

                    # Select from autocomplete
                    autocomplete_selector = self._selectors.get(
                        "location_autocomplete", ".autocomplete-results"
                    )
                    try:
                        first_result = self.browser.wait_for_element(
                            (By.CSS_SELECTOR, f"{autocomplete_selector} li:first-child"),
                            timeout=5,
                            condition="clickable",
                        )
                        first_result.click()
                        logger.info("Location selected from autocomplete")
                    except TimeoutException:
                        logger.warning("Autocomplete not available, proceeding...")

                except TimeoutException:
                    logger.warning("Location input not found")

            # Step 2: Fill personal information
            field_mapping = {
                "civilite": application.applicant.title or "M.",
                "nom": application.applicant.last_name or application.applicant.name.split()[-1],
                "prenom": application.applicant.first_name or application.applicant.name.split()[0],
                "adresse": application.applicant.address,
                "code_postal": application.applicant.postal_code,
                "commune": application.applicant.city,
                "email": application.applicant.email,
                "telephone": application.applicant.phone or "",
                "siret": application.applicant.tax_id if len(application.applicant.tax_id) == 14 else "",
                "objet_demande": application.installation.description,
                "lieu_installation": application.installation.location,
                "date_debut": application.installation.start_date.strftime("%d/%m/%Y"),
                "date_fin": (
                    application.installation.end_date.strftime("%d/%m/%Y")
                    if application.installation.end_date
                    else ""
                ),
                "superficie": str(application.installation.surface_area or ""),
            }

            for field_name, value in field_mapping.items():
                if not value:
                    continue

                try:
                    # Handle select fields differently
                    if field_name == "civilite":
                        selectors = [
                            f"select[name*='{field_name}']",
                            f"#select-{field_name}",
                        ]
                        for selector in selectors:
                            try:
                                select_element = self.browser.driver.find_element(
                                    By.CSS_SELECTOR, selector
                                )
                                select = Select(select_element)
                                select.select_by_visible_text(value)
                                logger.debug(f"Selected '{value}' for {field_name}")
                                break
                            except (NoSuchElementException, Exception):
                                continue
                    else:
                        # Regular input fields
                        selectors = [
                            f"input[name*='{field_name}']",
                            f"textarea[name*='{field_name}']",
                            f"#field-{field_name}",
                            f"[data-field='{field_name}']",
                        ]

                        for selector in selectors:
                            try:
                                self.browser.fill_field(
                                    (By.CSS_SELECTOR, selector),
                                    str(value),
                                )
                                logger.debug(f"Filled field '{field_name}'")
                                break
                            except Exception:
                                continue

                except Exception as e:
                    logger.warning(f"Error filling field '{field_name}': {e}")

            logger.info("Form filling completed")
            return True

        except Exception as e:
            logger.error(f"Error filling form: {e}")
            return False

    def upload_attachments(self, application: Application) -> bool:
        """
        Upload required attachments for the French form.

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
                    # Find file input
                    selectors = [
                        f"input[type='file'][name*='{attachment.document_type}']",
                        f"input[type='file'][data-document='{attachment.document_type}']",
                        f"#upload-{attachment.document_type}",
                        f".fr-upload input[type='file']",
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
                        time.sleep(2)
                    else:
                        if attachment.required:
                            logger.error(
                                f"Required upload field not found: {attachment.document_type}"
                            )
                            return False
                        logger.warning(
                            f"Optional upload field not found: {attachment.document_type}"
                        )

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
            submit_selector = self._selectors.get("submit_button", "#envoyer")
            self.browser.click((By.CSS_SELECTOR, submit_selector))

            logger.info("Submit button clicked, waiting for confirmation...")
            time.sleep(5)

            # Check for success message
            try:
                success_selector = self._selectors.get(
                    "success_message", ".fr-alert--success"
                )
                self.browser.wait_for_element(
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
                # Check for error
                error_selector = self._selectors.get(
                    "error_message", ".fr-alert--error"
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
            patterns = [
                "//span[contains(@class, 'reference')]",
                "//div[contains(text(), 'Numéro de référence')]//following-sibling::*",
                "//*[contains(text(), 'Référence:')]",
                ".numero-reference",
                "#submission-reference",
            ]

            for pattern in patterns:
                try:
                    if pattern.startswith("//"):
                        element = self.browser.driver.find_element(By.XPATH, pattern)
                    else:
                        element = self.browser.driver.find_element(
                            By.CSS_SELECTOR, pattern
                        )

                    text = element.text.strip()
                    if text:
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
                "receipt_download", ".telecharger-recepisse"
            )

            try:
                download_btn = self.browser.wait_for_element(
                    (By.CSS_SELECTOR, receipt_selector),
                    timeout=10,
                    condition="clickable",
                )
                download_btn.click()

                time.sleep(5)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                receipt_path = f"./data/output/receipt_france_{timestamp}.pdf"
                return receipt_path

            except TimeoutException:
                logger.warning("Receipt download button not found")
                return None

        except Exception as e:
            logger.error(f"Error downloading receipt: {e}")
            return None
