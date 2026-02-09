#!/usr/bin/env python3
"""
Diagnostic script for EU Registry Bot
Run this to identify issues with certificate, API, and batch processing
"""

import os
import sys
import json
import traceback

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_certificate(cert_path, cert_password):
    """Test certificate loading and validation."""
    print_section("CERTIFICATE TEST")

    try:
        from src.core.certificate import CertificateManager

        print(f"Certificate path: {cert_path}")
        print(f"File exists: {os.path.exists(cert_path)}")

        if not os.path.exists(cert_path):
            print("ERROR: Certificate file not found!")
            return False

        print(f"File size: {os.path.getsize(cert_path)} bytes")

        cert_manager = CertificateManager(cert_path, cert_password)

        print("\nLoading certificate...")
        if not cert_manager.load():
            print("ERROR: Failed to load certificate!")
            print("Possible causes:")
            print("  - Incorrect password")
            print("  - Corrupted certificate file")
            print("  - Invalid certificate format")
            return False

        print("Certificate loaded successfully!")

        info = cert_manager.get_info()
        if info:
            print(f"\nCertificate Info:")
            print(f"  Subject: {info.subject}")
            print(f"  Issuer: {info.issuer}")
            print(f"  Valid from: {info.not_valid_before}")
            print(f"  Valid until: {info.not_valid_after}")
            print(f"  Days until expiry: {info.days_until_expiry}")
            print(f"  Is valid: {info.is_valid}")

        if not cert_manager.is_valid():
            print("\nWARNING: Certificate is not valid or expired!")
            return False

        print("\n✓ Certificate validation PASSED")
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()
        return False

def test_data_reader(file_path):
    """Test data file reading."""
    print_section("DATA READER TEST")

    try:
        from src.utils import DATA_READER_SUPPORT

        print(f"Data file path: {file_path}")
        print(f"File exists: {os.path.exists(file_path)}")
        print(f"DATA_READER_SUPPORT: {DATA_READER_SUPPORT}")

        if not os.path.exists(file_path):
            print("ERROR: Data file not found!")
            return False

        if not DATA_READER_SUPPORT:
            print("ERROR: Data reader not supported. Install openpyxl, python-docx")
            return False

        from src.utils import DataReader

        print("\nReading data file...")
        reader = DataReader(file_path)
        records = reader.read_all()
        reader.close()

        print(f"Total records: {len(records)}")

        if len(records) > 0:
            print(f"\nFirst record:")
            r = records[0]
            print(f"  Name: {r.name}")
            print(f"  Code: {r.code}")
            print(f"  Province: {r.province}")
            print(f"  Status: {r.status}")

        print("\n✓ Data reader test PASSED")
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()
        return False

def test_application_creation():
    """Test application object creation."""
    print_section("APPLICATION CREATION TEST")

    try:
        from datetime import datetime
        from src.models.application import Application

        print("Creating test application...")

        app = Application.from_dict({
            "country": "portugal",
            "application_id": "TEST-001",
            "applicant": {
                "name": "Test Municipality",
                "tax_id": "AUTO-000001",
                "address": "Test Address",
                "city": "Test City",
                "email": "test@example.com",
            },
            "installation": {
                "description": "Test installation request",
                "location": "Test Location",
                "start_date": datetime.now().strftime("%Y-%m-%d"),
            },
        })

        print(f"Application created:")
        print(f"  Country: {app.country}")
        print(f"  Application ID: {app.application_id}")
        print(f"  Applicant: {app.applicant.name}")
        print(f"  Tax ID: {app.applicant.tax_id}")
        print(f"  Email: {app.applicant.email}")
        print(f"  Location: {app.installation.location}")

        print("\nValidating application...")
        is_valid, errors = app.validate()

        if not is_valid:
            print(f"Validation FAILED with errors:")
            for err in errors:
                print(f"  - {err}")
            return False

        print("✓ Application validation PASSED")
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()
        return False

def test_portal_initialization(country, cert_path, cert_password):
    """Test portal initialization."""
    print_section(f"PORTAL INITIALIZATION TEST ({country.upper()})")

    try:
        from src.core.certificate import CertificateManager

        cert_manager = CertificateManager(cert_path, cert_password)
        if not cert_manager.load():
            print("ERROR: Certificate loading failed")
            return False

        config_path = f"./config/{country}.yaml"
        print(f"Config path: {config_path}")
        print(f"Config exists: {os.path.exists(config_path)}")

        if not os.path.exists(config_path):
            print("ERROR: Config file not found!")
            return False

        if country == "portugal":
            from src.portals.portugal import PortugalPortal
            portal = PortugalPortal(config_path, cert_manager, headless=True, disable_circuit_breaker=True)
        elif country == "france":
            from src.portals.france import FrancePortal
            portal = FrancePortal(config_path, cert_manager, headless=True, disable_circuit_breaker=True)
        else:
            print(f"ERROR: Unknown country: {country}")
            return False

        print(f"\nPortal initialized:")
        print(f"  Portal name: {portal.portal_name}")
        print(f"  Country: {portal.country}")
        print(f"  Circuit breaker disabled: {portal.disable_circuit_breaker}")
        print(f"  Circuit breaker threshold: {portal.circuit_breaker.failure_threshold}")

        print("\n✓ Portal initialization PASSED")
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()
        return False

def test_api_server():
    """Test if API server is running."""
    print_section("API SERVER TEST")

    try:
        import requests

        url = "http://127.0.0.1:5000/api/health"
        print(f"Testing API endpoint: {url}")

        try:
            response = requests.get(url, timeout=5)
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.json()}")
            print("\n✓ API server is running")
            return True
        except requests.exceptions.ConnectionError:
            print("ERROR: Cannot connect to API server!")
            print("Make sure the server is running on port 5000")
            return False
        except Exception as e:
            print(f"ERROR: {e}")
            return False

    except ImportError:
        print("WARNING: 'requests' library not installed, skipping API test")
        return True

def main():
    print("\n" + "="*60)
    print("   EU REGISTRY BOT - DIAGNOSTIC TOOL")
    print("="*60)

    # Default test values - modify these for your setup
    CERT_PATH = os.environ.get("CERT_PATH", "./certificates/bionatur.p12")
    CERT_PASSWORD = os.environ.get("CERT_PASSWORD", "B09970666")
    DATA_FILE = os.environ.get("DATA_FILE", "./data/input/municipalities.xlsx")
    COUNTRY = os.environ.get("COUNTRY", "portugal")

    print(f"\nTest Configuration:")
    print(f"  CERT_PATH: {CERT_PATH}")
    print(f"  CERT_PASSWORD: {'*' * len(CERT_PASSWORD)}")
    print(f"  DATA_FILE: {DATA_FILE}")
    print(f"  COUNTRY: {COUNTRY}")

    results = {}

    # Run tests
    results['certificate'] = test_certificate(CERT_PATH, CERT_PASSWORD)
    results['application'] = test_application_creation()
    results['portal'] = test_portal_initialization(COUNTRY, CERT_PATH, CERT_PASSWORD)

    if os.path.exists(DATA_FILE):
        results['data_reader'] = test_data_reader(DATA_FILE)

    results['api'] = test_api_server()

    # Summary
    print_section("DIAGNOSTIC SUMMARY")

    all_passed = True
    for test, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {test.upper()}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n✓ All tests passed! The system should be ready.")
    else:
        print("\n✗ Some tests failed. Please check the errors above.")

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
