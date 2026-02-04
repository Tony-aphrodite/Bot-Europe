#!/usr/bin/env python3
"""
EU Registry Bot - Main Entry Point

Automated submission bot for EU government portals.
Supports Portugal (gov.pt) and France (Service-Public.fr).
"""

import argparse
import os
import sys
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

from src.core.certificate import CertificateManager
from src.core.logger import setup_logger
from src.core.scheduler import TaskScheduler
from src.models.application import Application
from src.portals.france import FrancePortal
from src.portals.portugal import PortugalPortal
from src.utils.file_handler import FileHandler

# Load environment variables
load_dotenv()

# Setup logger
logger = setup_logger(
    name="eu_registry_bot",
    level=os.getenv("LOG_LEVEL", "INFO"),
    log_file=os.getenv("LOG_FILE", "./logs/bot.log"),
)


def get_portal(country: str, certificate_manager: CertificateManager, headless: bool = True):
    """
    Get the appropriate portal instance for a country.

    Args:
        country: Country code ('portugal' or 'france')
        certificate_manager: Certificate manager instance
        headless: Run browser in headless mode

    Returns:
        Portal instance
    """
    portals = {
        "portugal": (PortugalPortal, "./config/portugal.yaml"),
        "france": (FrancePortal, "./config/france.yaml"),
    }

    if country not in portals:
        raise ValueError(f"Unsupported country: {country}. Supported: {list(portals.keys())}")

    portal_class, config_path = portals[country]
    return portal_class(config_path, certificate_manager, headless)


def process_single_application(
    application_file: str,
    certificate_path: str,
    certificate_password: str,
    headless: bool = True,
) -> bool:
    """
    Process a single application file.

    Args:
        application_file: Path to application YAML/JSON file
        certificate_path: Path to certificate file
        certificate_password: Certificate password
        headless: Run browser in headless mode

    Returns:
        True if submission successful
    """
    logger.info(f"Processing application: {application_file}")

    # Load application
    if application_file.endswith(".json"):
        application = FileHandler.load_application_from_json(application_file)
    else:
        application = FileHandler.load_application_from_yaml(application_file)

    if not application:
        logger.error("Failed to load application")
        return False

    # Validate
    is_valid, errors = application.validate()
    if not is_valid:
        logger.error(f"Validation errors: {errors}")
        return False

    # Setup certificate
    cert_manager = CertificateManager(certificate_path, certificate_password)
    if not cert_manager.load():
        logger.error("Failed to load certificate")
        return False

    if not cert_manager.is_valid():
        logger.error("Certificate is invalid or expired")
        return False

    cert_info = cert_manager.get_info()
    logger.info(f"Certificate loaded: {cert_info.subject}")
    logger.info(f"Valid until: {cert_info.not_valid_after} ({cert_info.days_until_expiry} days)")

    # Get portal and process
    try:
        portal = get_portal(application.country, cert_manager, headless)
        result = portal.process_application(application)

        # Save result
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = f"./data/output/result_{application.country}_{timestamp}.json"
        FileHandler.save_result_to_json(result, result_file)

        # Print summary
        print("\n" + "=" * 60)
        print(result.get_summary())
        print("=" * 60 + "\n")

        return result.is_successful()

    except Exception as e:
        logger.error(f"Error processing application: {e}")
        return False


def process_all_pending(
    input_dir: str,
    certificate_path: str,
    certificate_password: str,
    headless: bool = True,
) -> dict:
    """
    Process all pending applications in directory.

    Args:
        input_dir: Directory containing application files
        certificate_path: Path to certificate file
        certificate_password: Certificate password
        headless: Run browser in headless mode

    Returns:
        Dictionary with results summary
    """
    applications = FileHandler.list_pending_applications(input_dir)

    if not applications:
        logger.info("No pending applications found")
        return {"total": 0, "success": 0, "failed": 0}

    results = {"total": len(applications), "success": 0, "failed": 0, "details": []}

    for app_file in applications:
        success = process_single_application(
            app_file, certificate_path, certificate_password, headless
        )

        if success:
            results["success"] += 1
        else:
            results["failed"] += 1

        results["details"].append({"file": app_file, "success": success})

    logger.info(
        f"Processing complete: {results['success']}/{results['total']} successful"
    )
    return results


def run_scheduled(
    input_dir: str,
    certificate_path: str,
    certificate_password: str,
    hour: int = 9,
    minute: int = 0,
):
    """
    Run bot on a schedule.

    Args:
        input_dir: Directory containing application files
        certificate_path: Path to certificate file
        certificate_password: Certificate password
        hour: Hour to run (0-23)
        minute: Minute to run (0-59)
    """
    scheduler = TaskScheduler()

    def scheduled_task():
        logger.info("Running scheduled submission task...")
        process_all_pending(input_dir, certificate_path, certificate_password)

    scheduler.add_daily_task(
        task_id="daily_submission",
        func=scheduled_task,
        hour=hour,
        minute=minute,
    )

    logger.info(f"Scheduler started. Will run daily at {hour:02d}:{minute:02d}")
    logger.info("Press Ctrl+C to stop...")

    try:
        scheduler.start()
        # Keep the main thread alive
        import time

        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Stopping scheduler...")
        scheduler.stop()


def create_sample():
    """Create sample application files."""
    FileHandler.create_sample_application(
        "./data/input/sample_portugal.yaml", "portugal"
    )
    FileHandler.create_sample_application("./data/input/sample_france.yaml", "france")
    print("Sample application files created in ./data/input/")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="EU Registry Bot - Automated submission for EU government portals"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Submit command
    submit_parser = subparsers.add_parser("submit", help="Submit an application")
    submit_parser.add_argument(
        "application", help="Path to application file (YAML or JSON)"
    )
    submit_parser.add_argument(
        "--certificate",
        "-c",
        default=os.getenv("CERTIFICATE_PATH", "./certificates/certificate.p12"),
        help="Path to certificate file",
    )
    submit_parser.add_argument(
        "--password",
        "-p",
        default=os.getenv("CERTIFICATE_PASSWORD", ""),
        help="Certificate password",
    )
    submit_parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Show browser window (for debugging)",
    )

    # Process all command
    process_parser = subparsers.add_parser(
        "process-all", help="Process all pending applications"
    )
    process_parser.add_argument(
        "--input-dir",
        "-i",
        default="./data/input",
        help="Input directory with application files",
    )
    process_parser.add_argument(
        "--certificate",
        "-c",
        default=os.getenv("CERTIFICATE_PATH", "./certificates/certificate.p12"),
        help="Path to certificate file",
    )
    process_parser.add_argument(
        "--password",
        "-p",
        default=os.getenv("CERTIFICATE_PASSWORD", ""),
        help="Certificate password",
    )
    process_parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Show browser window",
    )

    # Schedule command
    schedule_parser = subparsers.add_parser(
        "schedule", help="Run bot on a daily schedule"
    )
    schedule_parser.add_argument(
        "--input-dir",
        "-i",
        default="./data/input",
        help="Input directory with application files",
    )
    schedule_parser.add_argument(
        "--certificate",
        "-c",
        default=os.getenv("CERTIFICATE_PATH", "./certificates/certificate.p12"),
        help="Path to certificate file",
    )
    schedule_parser.add_argument(
        "--password",
        "-p",
        default=os.getenv("CERTIFICATE_PASSWORD", ""),
        help="Certificate password",
    )
    schedule_parser.add_argument(
        "--hour",
        type=int,
        default=int(os.getenv("SCHEDULER_HOUR", "9")),
        help="Hour to run (0-23)",
    )
    schedule_parser.add_argument(
        "--minute",
        type=int,
        default=int(os.getenv("SCHEDULER_MINUTE", "0")),
        help="Minute to run (0-59)",
    )

    # Sample command
    subparsers.add_parser("sample", help="Create sample application files")

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate", help="Validate an application file"
    )
    validate_parser.add_argument("application", help="Path to application file")

    # Certificate info command
    cert_parser = subparsers.add_parser("cert-info", help="Show certificate information")
    cert_parser.add_argument(
        "--certificate",
        "-c",
        default=os.getenv("CERTIFICATE_PATH", "./certificates/certificate.p12"),
        help="Path to certificate file",
    )
    cert_parser.add_argument(
        "--password",
        "-p",
        default=os.getenv("CERTIFICATE_PASSWORD", ""),
        help="Certificate password",
    )

    args = parser.parse_args()

    if args.command == "submit":
        success = process_single_application(
            args.application,
            args.certificate,
            args.password,
            headless=not args.no_headless,
        )
        sys.exit(0 if success else 1)

    elif args.command == "process-all":
        results = process_all_pending(
            args.input_dir,
            args.certificate,
            args.password,
            headless=not args.no_headless,
        )
        sys.exit(0 if results["failed"] == 0 else 1)

    elif args.command == "schedule":
        run_scheduled(
            args.input_dir,
            args.certificate,
            args.password,
            args.hour,
            args.minute,
        )

    elif args.command == "sample":
        create_sample()

    elif args.command == "validate":
        if args.application.endswith(".json"):
            app = FileHandler.load_application_from_json(args.application)
        else:
            app = FileHandler.load_application_from_yaml(args.application)

        if app:
            is_valid, errors = app.validate()
            if is_valid:
                print("✓ Application is valid")
                sys.exit(0)
            else:
                print("✗ Validation errors:")
                for error in errors:
                    print(f"  - {error}")
                sys.exit(1)
        else:
            print("✗ Failed to load application file")
            sys.exit(1)

    elif args.command == "cert-info":
        cert_manager = CertificateManager(args.certificate, args.password)
        if cert_manager.load():
            info = cert_manager.get_info()
            print("\nCertificate Information:")
            print(f"  Subject: {info.subject}")
            print(f"  Issuer: {info.issuer}")
            print(f"  Serial: {info.serial_number}")
            print(f"  Valid From: {info.not_valid_before}")
            print(f"  Valid Until: {info.not_valid_after}")
            print(f"  Days Until Expiry: {info.days_until_expiry}")
            print(f"  Status: {'✓ Valid' if info.is_valid else '✗ Expired'}")
        else:
            print("✗ Failed to load certificate")
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
