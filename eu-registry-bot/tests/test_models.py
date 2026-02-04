"""
Tests for data models
"""

import pytest
from datetime import date

from src.models.application import Application, Applicant, InstallationDetails, Attachment
from src.models.result import SubmissionResult, SubmissionStatus


class TestApplicant:
    """Tests for Applicant model."""

    def test_create_applicant(self):
        applicant = Applicant(
            name="Test User",
            tax_id="12345678A",
            email="test@example.com",
        )

        assert applicant.name == "Test User"
        assert applicant.tax_id == "12345678A"
        assert applicant.email == "test@example.com"

    def test_applicant_optional_fields(self):
        applicant = Applicant(
            name="Test User",
            tax_id="12345678A",
            email="test@example.com",
            phone="+34 600 123 456",
            address="Test Address",
        )

        assert applicant.phone == "+34 600 123 456"
        assert applicant.address == "Test Address"


class TestInstallationDetails:
    """Tests for InstallationDetails model."""

    def test_create_installation(self):
        installation = InstallationDetails(
            description="Test installation",
            location="Test location",
            start_date=date(2024, 6, 1),
        )

        assert installation.description == "Test installation"
        assert installation.start_date == date(2024, 6, 1)

    def test_installation_with_end_date(self):
        installation = InstallationDetails(
            description="Test",
            location="Test",
            start_date=date(2024, 6, 1),
            end_date=date(2024, 6, 15),
        )

        assert installation.end_date == date(2024, 6, 15)


class TestApplication:
    """Tests for Application model."""

    @pytest.fixture
    def valid_application(self):
        return Application(
            applicant=Applicant(
                name="Test User",
                tax_id="12345678A",
                email="test@example.com",
            ),
            installation=InstallationDetails(
                description="Test installation",
                location="Test location",
                start_date=date(2024, 6, 1),
            ),
            country="portugal",
        )

    def test_validate_valid_application(self, valid_application):
        is_valid, errors = valid_application.validate()
        assert is_valid
        assert len(errors) == 0

    def test_validate_missing_name(self):
        app = Application(
            applicant=Applicant(name="", tax_id="123", email="test@example.com"),
            installation=InstallationDetails(
                description="Test",
                location="Test",
                start_date=date(2024, 6, 1),
            ),
            country="portugal",
        )

        is_valid, errors = app.validate()
        assert not is_valid
        assert "Applicant name is required" in errors

    def test_validate_invalid_country(self, valid_application):
        valid_application.country = "invalid_country"
        is_valid, errors = valid_application.validate()
        assert not is_valid
        assert any("Unsupported country" in e for e in errors)

    def test_to_dict(self, valid_application):
        data = valid_application.to_dict()
        assert data["country"] == "portugal"
        assert data["applicant"]["name"] == "Test User"


class TestSubmissionResult:
    """Tests for SubmissionResult model."""

    def test_create_success(self):
        result = SubmissionResult.create_success(
            reference_number="REF123",
            country="portugal",
            portal="gov.pt",
        )

        assert result.status == SubmissionStatus.SUBMITTED
        assert result.reference_number == "REF123"
        assert result.is_successful()

    def test_create_failure(self):
        result = SubmissionResult.create_failure(
            error_message="Test error",
            country="france",
            portal="service-public.fr",
        )

        assert result.status == SubmissionStatus.FAILED
        assert result.error_message == "Test error"
        assert not result.is_successful()

    def test_add_log(self):
        result = SubmissionResult(status=SubmissionStatus.IN_PROGRESS)
        result.add_log("Test message")

        assert len(result.log_entries) == 1
        assert "Test message" in result.log_entries[0]

    def test_get_summary(self):
        result = SubmissionResult.create_success(
            reference_number="REF123",
            country="portugal",
            portal="gov.pt",
        )

        summary = result.get_summary()
        assert "SUBMITTED" in summary
        assert "REF123" in summary
