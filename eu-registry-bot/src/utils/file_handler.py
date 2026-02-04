"""
File handling utilities
"""

import json
import os
from datetime import date, datetime
from typing import List, Optional

import yaml

from ..core.logger import setup_logger
from ..models.application import Application, Applicant, Attachment, InstallationDetails

logger = setup_logger(__name__)


class FileHandler:
    """
    Handles file operations for applications and results.
    """

    @staticmethod
    def load_application_from_yaml(file_path: str) -> Optional[Application]:
        """
        Load application data from YAML file.

        Args:
            file_path: Path to YAML file

        Returns:
            Application object or None
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            return FileHandler._parse_application_data(data)

        except Exception as e:
            logger.error(f"Error loading application from YAML: {e}")
            return None

    @staticmethod
    def load_application_from_json(file_path: str) -> Optional[Application]:
        """
        Load application data from JSON file.

        Args:
            file_path: Path to JSON file

        Returns:
            Application object or None
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            return FileHandler._parse_application_data(data)

        except Exception as e:
            logger.error(f"Error loading application from JSON: {e}")
            return None

    @staticmethod
    def _parse_application_data(data: dict) -> Application:
        """Parse application data from dictionary."""
        applicant_data = data.get("applicant", {})
        installation_data = data.get("installation", {})
        attachments_data = data.get("attachments", [])

        # Parse dates
        start_date = installation_data.get("start_date")
        if isinstance(start_date, str):
            start_date = date.fromisoformat(start_date)
        elif isinstance(start_date, datetime):
            start_date = start_date.date()

        end_date = installation_data.get("end_date")
        if end_date:
            if isinstance(end_date, str):
                end_date = date.fromisoformat(end_date)
            elif isinstance(end_date, datetime):
                end_date = end_date.date()

        applicant = Applicant(
            name=applicant_data.get("name", ""),
            tax_id=applicant_data.get("tax_id", ""),
            email=applicant_data.get("email", ""),
            phone=applicant_data.get("phone"),
            address=applicant_data.get("address", ""),
            postal_code=applicant_data.get("postal_code", ""),
            city=applicant_data.get("city", ""),
            country=applicant_data.get("country", ""),
            title=applicant_data.get("title"),
            first_name=applicant_data.get("first_name"),
            last_name=applicant_data.get("last_name"),
        )

        installation = InstallationDetails(
            description=installation_data.get("description", ""),
            location=installation_data.get("location", ""),
            start_date=start_date,
            end_date=end_date,
            surface_area=installation_data.get("surface_area"),
            installation_type=installation_data.get("installation_type"),
            road_type=installation_data.get("road_type"),
        )

        attachments = [
            Attachment(
                name=a.get("name", ""),
                file_path=a.get("file_path", ""),
                document_type=a.get("document_type", ""),
                required=a.get("required", True),
            )
            for a in attachments_data
        ]

        return Application(
            applicant=applicant,
            installation=installation,
            country=data.get("country", ""),
            attachments=attachments,
            application_id=data.get("application_id"),
            notes=data.get("notes"),
        )

    @staticmethod
    def save_result_to_json(result, file_path: str) -> bool:
        """
        Save submission result to JSON file.

        Args:
            result: SubmissionResult object
            file_path: Output file path

        Returns:
            True if saved successfully
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2, default=str)

            logger.info(f"Result saved to: {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error saving result: {e}")
            return False

    @staticmethod
    def list_pending_applications(input_dir: str) -> List[str]:
        """
        List all pending application files in directory.

        Args:
            input_dir: Directory to scan

        Returns:
            List of file paths
        """
        applications = []

        try:
            for filename in os.listdir(input_dir):
                if filename.endswith((".yaml", ".yml", ".json")):
                    file_path = os.path.join(input_dir, filename)
                    applications.append(file_path)

            logger.info(f"Found {len(applications)} pending applications")
            return sorted(applications)

        except Exception as e:
            logger.error(f"Error listing applications: {e}")
            return []

    @staticmethod
    def create_sample_application(output_path: str, country: str = "portugal") -> bool:
        """
        Create a sample application file for reference.

        Args:
            output_path: Output file path
            country: Target country

        Returns:
            True if created successfully
        """
        sample_data = {
            "country": country,
            "applicant": {
                "name": "Juan García López",
                "tax_id": "12345678A",
                "email": "juan.garcia@example.com",
                "phone": "+34 600 123 456",
                "address": "Calle Principal 123",
                "postal_code": "28001",
                "city": "Madrid",
                "country": "Spain",
                "title": "M.",
                "first_name": "Juan",
                "last_name": "García López",
            },
            "installation": {
                "description": "Instalación de carpa temporal para evento cultural",
                "location": "Plaza Mayor, Madrid",
                "start_date": "2024-06-01",
                "end_date": "2024-06-15",
                "surface_area": 50.0,
                "installation_type": "temporary_structure",
                "road_type": "commune",
            },
            "attachments": [
                {
                    "name": "Documento de Identidad",
                    "file_path": "./data/input/documents/id_document.pdf",
                    "document_type": "piece_identite",
                    "required": True,
                },
                {
                    "name": "Plano de Situación",
                    "file_path": "./data/input/documents/site_plan.pdf",
                    "document_type": "plan_situation",
                    "required": True,
                },
                {
                    "name": "Plano de Instalación",
                    "file_path": "./data/input/documents/installation_plan.pdf",
                    "document_type": "plan_installation",
                    "required": True,
                },
            ],
            "notes": "Evento cultural organizado por la Asociación Cultural Local",
        }

        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            if output_path.endswith(".json"):
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(sample_data, f, indent=2, ensure_ascii=False)
            else:
                with open(output_path, "w", encoding="utf-8") as f:
                    yaml.dump(sample_data, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"Sample application created: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Error creating sample application: {e}")
            return False
