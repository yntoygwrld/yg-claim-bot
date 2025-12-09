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


def main():
    """Main entry point - starts bot thread and API server"""
    logger.info("=" * 50)
    logger.info("YG CLAIM BOT + API SERVER")
    logger.info("=" * 50)

    # Start Telegram bot in background thread
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()
    logger.info("Telegram bot thread started")

    # Give bot time to initialize
    time.sleep(2)

    # Start Flask API server in main thread
    logger.info("Starting Flask API server...")
    from api_server import app

    port = int(os.environ.get('PORT', 8000))

    # Use production server settings
    if os.environ.get('KOYEB_SERVICE_NAME'):
        # Running on Koyeb - use gunicorn-like settings
        from waitress import serve
        logger.info(f"Starting production server on port {port}")
        serve(app, host='0.0.0.0', port=port, threads=4)
    else:
        # Local development
        logger.info(f"Starting development server on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)


if __name__ == '__main__':
    main()
