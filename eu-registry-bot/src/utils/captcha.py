"""
CAPTCHA detection and handling utilities
"""

import time
from enum import Enum
from typing import Optional, Callable
from dataclasses import dataclass

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException

from ..core.logger import setup_logger

logger = setup_logger(__name__)


class CaptchaType(Enum):
    """Types of CAPTCHA that may be encountered."""
    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    HCAPTCHA = "hcaptcha"
    IMAGE_CAPTCHA = "image_captcha"
    TEXT_CAPTCHA = "text_captcha"
    UNKNOWN = "unknown"


@dataclass
class CaptchaDetectionResult:
    """Result of CAPTCHA detection."""
    detected: bool
    captcha_type: CaptchaType
    element_selector: Optional[str] = None
    iframe_src: Optional[str] = None


class CaptchaDetector:
    """
    Detects various types of CAPTCHA on web pages.
    """

    # Common CAPTCHA selectors
    CAPTCHA_SELECTORS = {
        CaptchaType.RECAPTCHA_V2: [
            "iframe[src*='recaptcha']",
            ".g-recaptcha",
            "#recaptcha",
            "[data-sitekey]",
            "iframe[title*='reCAPTCHA']",
        ],
        CaptchaType.RECAPTCHA_V3: [
            ".grecaptcha-badge",
            "script[src*='recaptcha/api.js?render']",
        ],
        CaptchaType.HCAPTCHA: [
            "iframe[src*='hcaptcha']",
            ".h-captcha",
            "[data-hcaptcha-sitekey]",
        ],
        CaptchaType.IMAGE_CAPTCHA: [
            "img[src*='captcha']",
            "img[alt*='captcha']",
            ".captcha-image",
            "#captcha-img",
        ],
        CaptchaType.TEXT_CAPTCHA: [
            "input[name*='captcha']",
            "#captcha-input",
            ".captcha-input",
        ],
    }

    def __init__(self, driver: WebDriver):
        """
        Initialize CAPTCHA detector.

        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver

    def detect(self) -> CaptchaDetectionResult:
        """
        Detect if CAPTCHA is present on current page.

        Returns:
            CaptchaDetectionResult with detection info
        """
        for captcha_type, selectors in self.CAPTCHA_SELECTORS.items():
            for selector in selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element and element.is_displayed():
                        logger.warning(f"CAPTCHA detected: {captcha_type.value}")

                        iframe_src = None
                        if selector.startswith("iframe"):
                            iframe_src = element.get_attribute("src")

                        return CaptchaDetectionResult(
                            detected=True,
                            captcha_type=captcha_type,
                            element_selector=selector,
                            iframe_src=iframe_src,
                        )
                except NoSuchElementException:
                    continue
                except Exception as e:
                    logger.debug(f"Error checking selector {selector}: {e}")
                    continue

        return CaptchaDetectionResult(
            detected=False,
            captcha_type=CaptchaType.UNKNOWN,
        )

    def wait_for_manual_solve(
        self,
        timeout: int = 300,
        check_interval: int = 5,
        on_waiting: Optional[Callable] = None,
    ) -> bool:
        """
        Wait for user to manually solve CAPTCHA.

        Args:
            timeout: Maximum wait time in seconds
            check_interval: Seconds between checks
            on_waiting: Optional callback called while waiting

        Returns:
            True if CAPTCHA was solved (no longer detected)
        """
        logger.info(f"Waiting for CAPTCHA to be solved (timeout: {timeout}s)...")

        elapsed = 0
        while elapsed < timeout:
            result = self.detect()
            if not result.detected:
                logger.info("CAPTCHA solved!")
                return True

            if on_waiting:
                on_waiting(elapsed, timeout)

            time.sleep(check_interval)
            elapsed += check_interval

        logger.error("CAPTCHA solve timeout reached")
        return False


class CaptchaHandler:
    """
    Handles CAPTCHA encounters during automation.
    """

    def __init__(
        self,
        driver: WebDriver,
        auto_wait: bool = True,
        wait_timeout: int = 300,
    ):
        """
        Initialize CAPTCHA handler.

        Args:
            driver: Selenium WebDriver instance
            auto_wait: Automatically wait for manual solve
            wait_timeout: Timeout for manual solve wait
        """
        self.driver = driver
        self.detector = CaptchaDetector(driver)
        self.auto_wait = auto_wait
        self.wait_timeout = wait_timeout
        self._notification_callback: Optional[Callable] = None

    def set_notification_callback(self, callback: Callable) -> None:
        """
        Set callback for CAPTCHA notifications.

        Args:
            callback: Function called when CAPTCHA is detected
        """
        self._notification_callback = callback

    def check_and_handle(self) -> bool:
        """
        Check for CAPTCHA and handle if present.

        Returns:
            True if no CAPTCHA or CAPTCHA was solved
        """
        result = self.detector.detect()

        if not result.detected:
            return True

        logger.warning(f"CAPTCHA encountered: {result.captcha_type.value}")

        # Notify via callback
        if self._notification_callback:
            self._notification_callback(
                f"CAPTCHA detected ({result.captcha_type.value}). "
                "Please solve manually in the browser window."
            )

        if self.auto_wait:
            return self.detector.wait_for_manual_solve(
                timeout=self.wait_timeout,
                on_waiting=self._log_waiting_status,
            )

        return False

    def _log_waiting_status(self, elapsed: int, timeout: int) -> None:
        """Log waiting status."""
        remaining = timeout - elapsed
        if elapsed % 30 == 0:  # Log every 30 seconds
            logger.info(f"Waiting for CAPTCHA... ({remaining}s remaining)")
