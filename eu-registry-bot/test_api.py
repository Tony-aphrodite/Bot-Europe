#!/usr/bin/env python3
"""
Quick API Test Script for EU Registry Bot
Run this to verify the API server is working correctly
"""

import sys
import os
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    try:
        from flask import Flask
        print("  Flask: OK")
    except ImportError as e:
        print(f"  Flask: FAILED - {e}")
        return False

    try:
        from flask_cors import CORS
        print("  flask_cors: OK")
    except ImportError as e:
        print(f"  flask_cors: FAILED - {e}")
        return False

    try:
        from src.core.certificate import CertificateManager
        print("  CertificateManager: OK")
    except ImportError as e:
        print(f"  CertificateManager: FAILED - {e}")
        return False

    try:
        from src.utils import DATA_READER_SUPPORT, EXCEL_SUPPORT
        print(f"  DATA_READER_SUPPORT: {DATA_READER_SUPPORT}")
        print(f"  EXCEL_SUPPORT: {EXCEL_SUPPORT}")
    except ImportError as e:
        print(f"  Utils import: FAILED - {e}")
        return False

    try:
        from src.core.browser import BrowserManager
        print("  BrowserManager: OK")
    except ImportError as e:
        print(f"  BrowserManager: FAILED - {e}")
        return False

    return True


def test_api_server():
    """Test that the API server can start."""
    print("\nTesting API server startup...")
    try:
        import threading
        import requests
        from api.server import app

        # Start server in background
        def run_server():
            app.run(host="127.0.0.1", port=5001, debug=False, threaded=True, use_reloader=False)

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        # Wait for server to start
        time.sleep(2)

        # Test health endpoint
        try:
            response = requests.get("http://127.0.0.1:5001/api/health", timeout=5)
            if response.status_code == 200:
                print("  Health endpoint: OK")
                print(f"  Response: {response.json()}")
                return True
            else:
                print(f"  Health endpoint: FAILED (status {response.status_code})")
                return False
        except requests.exceptions.ConnectionError:
            print("  Health endpoint: FAILED (cannot connect)")
            return False

    except Exception as e:
        print(f"  API server: FAILED - {e}")
        return False


def test_certificate(cert_path, cert_password):
    """Test certificate loading."""
    print(f"\nTesting certificate: {cert_path}")
    if not os.path.exists(cert_path):
        print(f"  Certificate file not found!")
        return False

    try:
        from src.core.certificate import CertificateManager
        cert_manager = CertificateManager(cert_path, cert_password)

        if cert_manager.load():
            print("  Load: OK")
            info = cert_manager.get_info()
            if info:
                print(f"  Subject: {info.subject[:50]}...")
                print(f"  Valid: {info.is_valid}")
                print(f"  Expiry: {info.days_until_expiry} days")
                return True
            else:
                print("  Get info: FAILED")
                return False
        else:
            print("  Load: FAILED (check password)")
            return False

    except Exception as e:
        print(f"  Certificate test: FAILED - {e}")
        return False


def main():
    print("=" * 60)
    print("  EU Registry Bot - API Quick Test")
    print("=" * 60)

    results = {}

    # Test imports
    results['imports'] = test_imports()

    # Test certificate (default path)
    cert_path = os.environ.get("CERT_PATH", "./certificates/bionatur.p12")
    cert_password = os.environ.get("CERT_PASSWORD", "B09970666")

    if os.path.exists(cert_path):
        results['certificate'] = test_certificate(cert_path, cert_password)
    else:
        print(f"\nSkipping certificate test (file not found: {cert_path})")
        results['certificate'] = None

    # Test API server
    results['api'] = test_api_server()

    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)

    all_pass = True
    for test, result in results.items():
        if result is None:
            status = "SKIPPED"
        elif result:
            status = "PASS"
        else:
            status = "FAIL"
            all_pass = False
        print(f"  {test}: {status}")

    print("\n")
    if all_pass:
        print("All tests passed! The API should work correctly.")
        print("\nTo start the API server manually, run:")
        print("  python api/server.py")
    else:
        print("Some tests failed. Please check the errors above.")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
