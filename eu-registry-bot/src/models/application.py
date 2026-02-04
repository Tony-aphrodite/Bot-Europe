"""
Application data models
"""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


@dataclass
class Applicant:
    """Applicant information."""

    # Personal/Company identification
    name: str
    tax_id: str  # NIF (Portugal) / SIRET (France)

    # Contact information
    email: str
    phone: Optional[str] = None

    # Address
    address: str = ""
    postal_code: str = ""
    city: str = ""
    country: str = ""

    # Optional fields
    title: Optional[str] = None  # M. / Mme (France)
    first_name: Optional[str] = None
    last_name: Optional[str] = None


@dataclass
class InstallationDetails:
    """Installation request details."""

    # Description
    description: str
    location: str

    # Dates
    start_date: date
    end_date: Optional[date] = None

    # Additional details
    surface_area: Optional[float] = None  # in m²
    installation_type: Optional[str] = None

    # Location classification (for France)
    road_type: Optional[str] = None  # commune, metropolitaine, departementale, nationale


@dataclass
class Attachment:
    """Document attachment."""

    name: str
    file_path: str
    document_type: str  # e.g., "piece_identite", "plan_installation"
    required: bool = True


@dataclass
class Application:
    """Complete application for public road installation permit."""

    # Core data
    applicant: Applicant
    installation: InstallationDetails

    # Target country
    country: str  # "portugal" or "france"

    # Attachments
    attachments: List[Attachment] = field(default_factory=list)

    # Metadata
    application_id: Optional[str] = None
    created_at: Optional[str] = None
    notes: Optional[str] = None

    def validate(self) -> tuple[bool, List[str]]:
        """
        Validate the application data.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        # Validate applicant
        if not self.applicant.name:
            errors.append("Applicant name is required")
        if not self.applicant.tax_id:
            errors.append("Tax ID (NIF/SIRET) is required")
        if not self.applicant.email:
            errors.append("Email is required")

        # Validate installation details
        if not self.installation.description:
            errors.append("Installation description is required")
        if not self.installation.location:
            errors.append("Installation location is required")
        if not self.installation.start_date:
            errors.append("Start date is required")

        # Validate country
        if self.country not in ["portugal", "france"]:
            errors.append(f"Unsupported country: {self.country}")

        # Validate attachments
        required_attachments = [a for a in self.attachments if a.required]
        for attachment in required_attachments:
            import os

            if not os.path.exists(attachment.file_path):
                errors.append(f"Required attachment not found: {attachment.name}")

        return (len(errors) == 0, errors)

    def to_dict(self) -> dict:
        """Convert application to dictionary."""
        return {
            "applicant": {
                "name": self.applicant.name,
                "tax_id": self.applicant.tax_id,
                "email": self.applicant.email,
                "phone": self.applicant.phone,
                "address": self.applicant.address,
                "postal_code": self.applicant.postal_code,
                "city": self.applicant.city,
                "country": self.applicant.country,
            },
            "installation": {
                "description": self.installation.description,
                "location": self.installation.location,
                "start_date": self.installation.start_date.isoformat(),
                "end_date": (
                    self.installation.end_date.isoformat()
                    if self.installation.end_date
                    else None
                ),
                "surface_area": self.installation.surface_area,
            },
            "country": self.country,
            "attachments": [
                {"name": a.name, "file_path": a.file_path, "type": a.document_type}
                for a in self.attachments
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Application":
        """Create application from dictionary."""
        applicant_data = data.get("applicant", {})
        installation_data = data.get("installation", {})

        applicant = Applicant(
            name=applicant_data.get("name", ""),
            tax_id=applicant_data.get("tax_id", ""),
            email=applicant_data.get("email", ""),
            phone=applicant_data.get("phone"),
            address=applicant_data.get("address", ""),
            postal_code=applicant_data.get("postal_code", ""),
            city=applicant_data.get("city", ""),
            country=applicant_data.get("country", ""),
        )

        installation = InstallationDetails(
            description=installation_data.get("description", ""),
            location=installation_data.get("location", ""),
            start_date=date.fromisoformat(installation_data.get("start_date", "")),
            end_date=(
                date.fromisoformat(installation_data["end_date"])
                if installation_data.get("end_date")
                else None
            ),
            surface_area=installation_data.get("surface_area"),
        )

        attachments = [
            Attachment(
                name=a.get("name", ""),
                file_path=a.get("file_path", ""),
                document_type=a.get("type", ""),
            )
            for a in data.get("attachments", [])
        ]

        return cls(
            applicant=applicant,
            installation=installation,
            country=data.get("country", ""),
            attachments=attachments,
            application_id=data.get("application_id"),
        )
