#!/usr/bin/env python3
"""
Flask API Server for EU Registry Bot Desktop Application
"""

import os
import sys
import json
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.certificate import CertificateManager
from src.core.logger import setup_logger
from src.core.scheduler import TaskScheduler
from src.models.application import Application
from src.models.result import SubmissionResult, SubmissionStatus
from src.portals.portugal import PortugalPortal
from src.portals.france import FrancePortal
from src.utils.file_handler import FileHandler

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Setup logger
logger = setup_logger("api_server")

# Global state
bot_state = {
    "status": "idle",  # idle, running, error
    "current_task": None,
    "progress": 0,
    "last_result": None,
    "logs": [],
    "scheduler_active": False,
}

# Scheduler instance
scheduler = None


def add_log(message: str, level: str = "info"):
    """Add a log entry to the state."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "message": message,
    }
    bot_state["logs"].append(entry)
    # Keep only last 100 logs
    if len(bot_state["logs"]) > 100:
        bot_state["logs"] = bot_state["logs"][-100:]
    logger.info(message)


# =============================================================================
# Health & Status Endpoints
# =============================================================================

@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


@app.route("/api/status", methods=["GET"])
def get_status():
    """Get current bot status."""
    return jsonify({
        "status": bot_state["status"],
        "current_task": bot_state["current_task"],
        "progress": bot_state["progress"],
        "scheduler_active": bot_state["scheduler_active"],
        "last_result": bot_state["last_result"],
    })


@app.route("/api/logs", methods=["GET"])
def get_logs():
    """Get recent logs."""
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"logs": bot_state["logs"][-limit:]})


# =============================================================================
# Certificate Endpoints
# =============================================================================

@app.route("/api/certificate/info", methods=["POST"])
def get_certificate_info():
    """Get certificate information."""
    data = request.json
    cert_path = data.get("path")
    cert_password = data.get("password", "")

    if not cert_path or not os.path.exists(cert_path):
        return jsonify({"error": "Certificate file not found"}), 400

    try:
        cert_manager = CertificateManager(cert_path, cert_password)
        if not cert_manager.load():
            return jsonify({"error": "Failed to load certificate. Check password."}), 400

        info = cert_manager.get_info()
        return jsonify({
            "subject": info.subject,
            "issuer": info.issuer,
            "serial_number": str(info.serial_number),
            "valid_from": info.not_valid_before.isoformat(),
            "valid_until": info.not_valid_after.isoformat(),
            "days_until_expiry": info.days_until_expiry,
            "is_valid": info.is_valid,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/certificate/validate", methods=["POST"])
def validate_certificate():
    """Validate a certificate."""
    data = request.json
    cert_path = data.get("path")
    cert_password = data.get("password", "")

    if not cert_path:
        return jsonify({"valid": False, "error": "No certificate path provided"}), 400

    try:
        cert_manager = CertificateManager(cert_path, cert_password)
        if cert_manager.load() and cert_manager.is_valid():
            return jsonify({"valid": True})
        return jsonify({"valid": False, "error": "Certificate invalid or expired"})
    except Exception as e:
        return jsonify({"valid": False, "error": str(e)})


# =============================================================================
# Application Endpoints
# =============================================================================

@app.route("/api/applications", methods=["GET"])
def list_applications():
    """List all application files."""
    input_dir = request.args.get("dir", "./data/input")
    try:
        files = FileHandler.list_pending_applications(input_dir)
        applications = []
        for f in files:
            try:
                if f.endswith(".json"):
                    app_data = FileHandler.load_application_from_json(f)
                else:
                    app_data = FileHandler.load_application_from_yaml(f)
                if app_data:
                    applications.append({
                        "file": f,
                        "country": app_data.country,
                        "applicant": app_data.applicant.name,
                        "description": app_data.installation.description[:50] + "..."
                            if len(app_data.installation.description) > 50
                            else app_data.installation.description,
                    })
            except Exception:
                pass
        return jsonify({"applications": applications})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/applications/validate", methods=["POST"])
def validate_application():
    """Validate an application file."""
    data = request.json
    file_path = data.get("file")

    if not file_path or not os.path.exists(file_path):
        return jsonify({"valid": False, "errors": ["File not found"]}), 400

    try:
        if file_path.endswith(".json"):
            app_data = FileHandler.load_application_from_json(file_path)
        else:
            app_data = FileHandler.load_application_from_yaml(file_path)

        if not app_data:
            return jsonify({"valid": False, "errors": ["Failed to parse file"]})

        is_valid, errors = app_data.validate()
        return jsonify({"valid": is_valid, "errors": errors})
    except Exception as e:
        return jsonify({"valid": False, "errors": [str(e)]})


@app.route("/api/applications/sample", methods=["POST"])
def create_sample_application():
    """Create a sample application file."""
    data = request.json
    country = data.get("country", "portugal")
    output_path = data.get("path", f"./data/input/sample_{country}.yaml")

    try:
        FileHandler.create_sample_application(output_path, country)
        return jsonify({"success": True, "path": output_path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Submission Endpoints
# =============================================================================

def run_submission(application_file: str, cert_path: str, cert_password: str, headless: bool = True):
    """Background task to run submission."""
    global bot_state

    try:
        bot_state["status"] = "running"
        bot_state["progress"] = 0
        add_log(f"Starting submission: {application_file}")

        # Load application
        bot_state["current_task"] = "Loading application..."
        bot_state["progress"] = 10

        if application_file.endswith(".json"):
            application = FileHandler.load_application_from_json(application_file)
        else:
            application = FileHandler.load_application_from_yaml(application_file)

        if not application:
            raise Exception("Failed to load application file")

        add_log(f"Application loaded: {application.applicant.name}")

        # Validate
        bot_state["current_task"] = "Validating application..."
        bot_state["progress"] = 20
        is_valid, errors = application.validate()
        if not is_valid:
            raise Exception(f"Validation failed: {', '.join(errors)}")

        add_log("Application validated")

        # Load certificate
        bot_state["current_task"] = "Loading certificate..."
        bot_state["progress"] = 30
        cert_manager = CertificateManager(cert_path, cert_password)
        if not cert_manager.load() or not cert_manager.is_valid():
            raise Exception("Certificate invalid or expired")

        add_log("Certificate loaded and verified")

        # Get portal
        bot_state["current_task"] = "Connecting to portal..."
        bot_state["progress"] = 40

        config_path = f"./config/{application.country}.yaml"
        if application.country == "portugal":
            portal = PortugalPortal(config_path, cert_manager, headless)
        elif application.country == "france":
            portal = FrancePortal(config_path, cert_manager, headless)
        else:
            raise Exception(f"Unsupported country: {application.country}")

        add_log(f"Portal initialized: {portal.portal_name}")

        # Process application
        bot_state["current_task"] = "Processing application..."
        bot_state["progress"] = 50

        result = portal.process_application(application)

        bot_state["progress"] = 90

        # Save result
        bot_state["current_task"] = "Saving results..."
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = f"./data/output/result_{application.country}_{timestamp}.json"
        FileHandler.save_result_to_json(result, result_file)

        bot_state["progress"] = 100
        bot_state["last_result"] = result.to_dict()
        bot_state["status"] = "idle"
        bot_state["current_task"] = None

        if result.is_successful():
            add_log(f"Submission successful! Reference: {result.reference_number}", "success")
        else:
            add_log(f"Submission failed: {result.error_message}", "error")

    except Exception as e:
        bot_state["status"] = "error"
        bot_state["current_task"] = None
        bot_state["last_result"] = {"error": str(e)}
        add_log(f"Error: {str(e)}", "error")


@app.route("/api/submit", methods=["POST"])
def submit_application():
    """Submit an application."""
    if bot_state["status"] == "running":
        return jsonify({"error": "A submission is already in progress"}), 400

    data = request.json
    application_file = data.get("application")
    cert_path = data.get("certificate_path")
    cert_password = data.get("certificate_password", "")
    headless = data.get("headless", True)

    if not application_file or not cert_path:
        return jsonify({"error": "Missing required parameters"}), 400

    # Run in background thread
    thread = threading.Thread(
        target=run_submission,
        args=(application_file, cert_path, cert_password, headless)
    )
    thread.start()

    return jsonify({"message": "Submission started", "status": "running"})


@app.route("/api/submit/cancel", methods=["POST"])
def cancel_submission():
    """Cancel current submission (limited support)."""
    bot_state["status"] = "idle"
    bot_state["current_task"] = None
    add_log("Submission cancelled by user", "warning")
    return jsonify({"message": "Cancellation requested"})


# =============================================================================
# Results Endpoints
# =============================================================================

@app.route("/api/results", methods=["GET"])
def list_results():
    """List submission results."""
    output_dir = "./data/output"
    results = []

    try:
        for filename in os.listdir(output_dir):
            if filename.startswith("result_") and filename.endswith(".json"):
                filepath = os.path.join(output_dir, filename)
                with open(filepath, "r") as f:
                    data = json.load(f)
                    results.append({
                        "file": filepath,
                        "filename": filename,
                        "status": data.get("status"),
                        "country": data.get("country"),
                        "reference": data.get("reference_number"),
                        "submitted_at": data.get("submitted_at"),
                    })

        # Sort by date descending
        results.sort(key=lambda x: x.get("submitted_at") or "", reverse=True)
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/results/<path:filename>", methods=["GET"])
def get_result(filename):
    """Get a specific result."""
    filepath = os.path.join("./data/output", filename)
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return jsonify(json.load(f))
    return jsonify({"error": "Result not found"}), 404


# =============================================================================
# Scheduler Endpoints
# =============================================================================

@app.route("/api/scheduler/start", methods=["POST"])
def start_scheduler():
    """Start the scheduler."""
    global scheduler

    data = request.json
    hour = data.get("hour", 9)
    minute = data.get("minute", 0)
    input_dir = data.get("input_dir", "./data/input")
    cert_path = data.get("certificate_path")
    cert_password = data.get("certificate_password", "")

    if not cert_path:
        return jsonify({"error": "Certificate path required"}), 400

    try:
        if scheduler:
            scheduler.stop()

        scheduler = TaskScheduler()

        def scheduled_task():
            applications = FileHandler.list_pending_applications(input_dir)
            for app_file in applications:
                run_submission(app_file, cert_path, cert_password)

        scheduler.add_daily_task(
            task_id="daily_submission",
            func=scheduled_task,
            hour=hour,
            minute=minute,
        )

        scheduler.start()
        bot_state["scheduler_active"] = True

        add_log(f"Scheduler started: daily at {hour:02d}:{minute:02d}")
        return jsonify({"message": "Scheduler started", "schedule": f"{hour:02d}:{minute:02d}"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/scheduler/stop", methods=["POST"])
def stop_scheduler():
    """Stop the scheduler."""
    global scheduler

    if scheduler:
        scheduler.stop()
        scheduler = None

    bot_state["scheduler_active"] = False
    add_log("Scheduler stopped")
    return jsonify({"message": "Scheduler stopped"})


@app.route("/api/scheduler/status", methods=["GET"])
def scheduler_status():
    """Get scheduler status."""
    tasks = []
    if scheduler:
        tasks = scheduler.list_tasks()

    return jsonify({
        "active": bot_state["scheduler_active"],
        "tasks": tasks,
    })


# =============================================================================
# Settings Endpoints
# =============================================================================

@app.route("/api/settings", methods=["GET"])
def get_settings():
    """Get current settings."""
    settings_file = "./config/settings.yaml"
    if os.path.exists(settings_file):
        import yaml
        with open(settings_file, "r") as f:
            return jsonify(yaml.safe_load(f))
    return jsonify({})


@app.route("/api/settings", methods=["POST"])
def save_settings():
    """Save settings."""
    data = request.json
    settings_file = "./config/settings.yaml"

    try:
        import yaml
        with open(settings_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
        return jsonify({"message": "Settings saved"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    port = int(os.environ.get("FLASK_PORT", 5000))
    add_log(f"API Server starting on port {port}")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
