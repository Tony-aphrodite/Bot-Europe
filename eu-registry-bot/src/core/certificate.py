"""
Certificate management for digital signatures and authentication
"""

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

from .logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class CertificateInfo:
    """Certificate information dataclass."""

    subject: str
    issuer: str
    serial_number: int
    not_valid_before: datetime
    not_valid_after: datetime
    is_valid: bool
    days_until_expiry: int


class CertificateManager:
    """
    Manages digital certificates for portal authentication.
    """

    def __init__(self, certificate_path: str, password: Optional[str] = None):
        """
        Initialize certificate manager.

        Args:
            certificate_path: Path to .p12 or .pfx certificate file
            password: Certificate password
        """
        self.certificate_path = certificate_path
        self.password = password.encode() if password else None
        self._private_key = None
        self._certificate = None
        self._additional_certs = None

    def load(self) -> bool:
        """
        Load the certificate from file.

        Returns:
            True if loaded successfully
        """
        if not os.path.exists(self.certificate_path):
            logger.error(f"Certificate file not found: {self.certificate_path}")
            return False

        try:
            with open(self.certificate_path, "rb") as f:
                pfx_data = f.read()

            (
                self._private_key,
                self._certificate,
                self._additional_certs,
            ) = pkcs12.load_key_and_certificates(pfx_data, self.password)

            logger.info(f"Certificate loaded successfully: {self.certificate_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load certificate: {e}")
            return False

    def get_info(self) -> Optional[CertificateInfo]:
        """
        Get certificate information.

        Returns:
            CertificateInfo object or None if not loaded
        """
        if not self._certificate:
            logger.warning("Certificate not loaded. Call load() first.")
            return None

        now = datetime.utcnow()

        # Handle both old and new cryptography library versions
        # New versions (>=37.0.0) use not_valid_after_utc, old versions use not_valid_after
        try:
            not_valid_before = self._certificate.not_valid_before_utc
            not_valid_after = self._certificate.not_valid_after_utc
        except AttributeError:
            # Fallback for older cryptography versions
            not_valid_before = self._certificate.not_valid_before
            not_valid_after = self._certificate.not_valid_after

        # Remove timezone info for comparison
        if hasattr(not_valid_after, 'tzinfo') and not_valid_after.tzinfo is not None:
            not_valid_after_naive = not_valid_after.replace(tzinfo=None)
        else:
            not_valid_after_naive = not_valid_after

        days_until_expiry = (not_valid_after_naive - now).days

        return CertificateInfo(
            subject=self._certificate.subject.rfc4514_string(),
            issuer=self._certificate.issuer.rfc4514_string(),
            serial_number=self._certificate.serial_number,
            not_valid_before=not_valid_before,
            not_valid_after=not_valid_after,
            is_valid=now < not_valid_after_naive,
            days_until_expiry=days_until_expiry,
        )

    def is_valid(self) -> bool:
        """
        Check if certificate is currently valid.

        Returns:
            True if certificate is valid and not expired
        """
        info = self.get_info()
        if not info:
            return False

        if not info.is_valid:
            logger.warning("Certificate has expired!")
            return False

        if info.days_until_expiry < 30:
            logger.warning(f"Certificate expires in {info.days_until_expiry} days!")

        return True

    def export_pem(self, output_path: str) -> bool:
        """
        Export certificate to PEM format.

        Args:
            output_path: Path for output PEM file

        Returns:
            True if exported successfully
        """
        if not self._certificate:
            logger.error("Certificate not loaded")
            return False

        try:
            pem_data = self._certificate.public_bytes(serialization.Encoding.PEM)
            with open(output_path, "wb") as f:
                f.write(pem_data)
            logger.info(f"Certificate exported to PEM: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export certificate: {e}")
            return False

    def get_subject_cn(self) -> Optional[str]:
        """
        Get the Common Name (CN) from certificate subject.

        Returns:
            Common Name string or None
        """
        if not self._certificate:
            return None

        try:
            cn = self._certificate.subject.get_attributes_for_oid(
                x509.oid.NameOID.COMMON_NAME
            )
            return cn[0].value if cn else None
        except Exception:
            return None

    def get_certificate_for_browser(self) -> tuple:
        """
        Get certificate data formatted for browser use.

        Returns:
            Tuple of (certificate_path, password) for browser configuration
        """
        return (self.certificate_path, self.password.decode() if self.password else "")

    def __repr__(self) -> str:
        info = self.get_info()
        if info:
            return f"CertificateManager(subject='{info.subject}', valid={info.is_valid})"
        return f"CertificateManager(path='{self.certificate_path}', loaded=False)"
