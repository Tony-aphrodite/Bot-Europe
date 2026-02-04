"""
Browser management for Selenium automation
"""

import os
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from .logger import setup_logger

logger = setup_logger(__name__)


class BrowserManager:
    """
    Manages Selenium WebDriver instance with certificate support.
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 30,
        download_dir: Optional[str] = None,
        certificate_path: Optional[str] = None,
    ):
        """
        Initialize browser manager.

        Args:
            headless: Run browser in headless mode
            timeout: Default timeout for waits
            download_dir: Directory for downloads
            certificate_path: Path to client certificate (.p12/.pfx)
        """
        self.headless = headless
        self.timeout = timeout
        self.download_dir = download_dir or os.path.join(os.getcwd(), "data", "output")
        self.certificate_path = certificate_path
        self.driver: Optional[webdriver.Chrome] = None

    def _create_options(self) -> ChromeOptions:
        """Create Chrome options with necessary configurations."""
        options = ChromeOptions()

        if self.headless:
            options.add_argument("--headless=new")

        # Basic options
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        # Language settings
        options.add_argument("--lang=en-US")
        options.add_experimental_option(
            "prefs",
            {
                "intl.accept_languages": "en-US,en,pt,fr",
                "download.default_directory": self.download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
            },
        )

        # Certificate handling
        if self.certificate_path:
            # Note: Chrome requires certificate to be installed in system store
            # or use AutoSelectCertificateForUrls policy
            options.add_argument(f"--ssl-client-certificate-file={self.certificate_path}")
            logger.info(f"Certificate configured: {self.certificate_path}")

        # Disable automation detection
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--disable-blink-features=AutomationControlled")

        return options

    def start(self) -> webdriver.Chrome:
        """
        Start the browser instance.

        Returns:
            WebDriver instance
        """
        if self.driver:
            logger.warning("Browser already running, returning existing instance")
            return self.driver

        logger.info("Starting browser...")

        options = self._create_options()
        service = ChromeService(ChromeDriverManager().install())

        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.implicitly_wait(10)
        self.driver.set_page_load_timeout(60)

        logger.info("Browser started successfully")
        return self.driver

    def stop(self) -> None:
        """Stop and close the browser instance."""
        if self.driver:
            logger.info("Stopping browser...")
            self.driver.quit()
            self.driver = None
            logger.info("Browser stopped")

    def navigate(self, url: str) -> None:
        """
        Navigate to a URL.

        Args:
            url: Target URL
        """
        if not self.driver:
            raise RuntimeError("Browser not started. Call start() first.")

        logger.info(f"Navigating to: {url}")
        self.driver.get(url)

    def wait_for_element(
        self,
        locator: tuple,
        timeout: Optional[int] = None,
        condition: str = "presence",
    ):
        """
        Wait for an element to be present/visible/clickable.

        Args:
            locator: Tuple of (By.XXX, "selector")
            timeout: Wait timeout in seconds
            condition: "presence", "visible", or "clickable"

        Returns:
            WebElement when found
        """
        if not self.driver:
            raise RuntimeError("Browser not started. Call start() first.")

        timeout = timeout or self.timeout
        wait = WebDriverWait(self.driver, timeout)

        conditions = {
            "presence": EC.presence_of_element_located,
            "visible": EC.visibility_of_element_located,
            "clickable": EC.element_to_be_clickable,
        }

        condition_func = conditions.get(condition, EC.presence_of_element_located)
        return wait.until(condition_func(locator))

    def fill_field(self, locator: tuple, value: str, clear: bool = True) -> None:
        """
        Fill a form field.

        Args:
            locator: Tuple of (By.XXX, "selector")
            value: Value to enter
            clear: Clear field before entering
        """
        element = self.wait_for_element(locator, condition="visible")
        if clear:
            element.clear()
        element.send_keys(value)
        logger.debug(f"Filled field {locator[1]} with value")

    def click(self, locator: tuple) -> None:
        """
        Click an element.

        Args:
            locator: Tuple of (By.XXX, "selector")
        """
        element = self.wait_for_element(locator, condition="clickable")
        element.click()
        logger.debug(f"Clicked element: {locator[1]}")

    def take_screenshot(self, filename: str) -> str:
        """
        Take a screenshot.

        Args:
            filename: Screenshot filename

        Returns:
            Path to saved screenshot
        """
        if not self.driver:
            raise RuntimeError("Browser not started. Call start() first.")

        filepath = os.path.join(self.download_dir, filename)
        self.driver.save_screenshot(filepath)
        logger.info(f"Screenshot saved: {filepath}")
        return filepath

    def get_page_source(self) -> str:
        """Get current page HTML source."""
        if not self.driver:
            raise RuntimeError("Browser not started. Call start() first.")
        return self.driver.page_source

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
