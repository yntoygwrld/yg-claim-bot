#!/usr/bin/env python3
"""
Combined runner for YG Claim Bot + API Server

This script runs both:
1. The Telegram bot (in a separate thread)
2. The Flask API server (main thread with gunicorn)

For Koyeb deployment, this allows a single service to handle both.
"""

import os
import sys
import threading
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_telegram_bot():
    """Run the Telegram bot in a separate thread"""
    logger.info("Starting Telegram bot...")
    try:
        # Import and run bot
        import bot

        # bot.main() is a blocking function that runs polling
        bot.main()
    except Exception as e:
        logger.exception(f"Telegram bot error: {e}")
        # Don't crash the whole service if bot fails
        time.sleep(30)
        run_telegram_bot()  # Retry


def run_flask_server():
    """Run Flask API server"""
    from api_server import app
    port = int(os.environ.get('PORT', 8000))

    if os.environ.get('KOYEB_SERVICE_NAME'):
        # Running on Koyeb - use waitress
        from waitress import serve
        logger.info(f"Starting production server on port {port}")
        serve(app, host='0.0.0.0', port=port, threads=4)
    else:
        # Local development
        logger.info(f"Starting development server on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)


def main():
    """Main entry point - starts API server FIRST, then bot"""
    logger.info("=" * 50)
    logger.info("YG CLAIM BOT + API SERVER")
    logger.info("=" * 50)

    # Import Flask app early to catch any import errors
    logger.info("Importing Flask app...")
    from api_server import app
    logger.info("Flask app imported successfully")

    port = int(os.environ.get('PORT', 8000))

    # Start Flask API server FIRST in a thread (for health checks)
    logger.info(f"Starting Flask API server on port {port}...")
    flask_thread = threading.Thread(target=run_flask_server, daemon=True)
    flask_thread.start()

    # Wait for Flask to be ready (bind to port)
    time.sleep(1)
    logger.info("Flask server thread started")

    # Now start Telegram bot in main thread (blocking)
    logger.info("Starting Telegram bot...")
    run_telegram_bot()


if __name__ == '__main__':
    main()
