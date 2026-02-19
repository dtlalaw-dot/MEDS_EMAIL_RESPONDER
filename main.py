"""MEDS Email Auto-Responder — Main entry point and polling loop.

Monitors a Microsoft 365 mailbox for new emails, looks up the sender's case
in Filevine, and sends an auto-response with case phase/status information.
"""

import argparse
import logging
import signal
import sys
import time

from config import Config
from email_client import EmailClient
from filevine_scraper import FilevineScraper
from responder import build_response

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("meds_responder")

# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------
_running = True


def _shutdown(signum, frame):
    global _running
    logger.info("Received signal %s — shutting down gracefully…", signum)
    _running = False


signal.signal(signal.SIGINT, _shutdown)
signal.signal(signal.SIGTERM, _shutdown)


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------
def process_emails(email_client: EmailClient, scraper: FilevineScraper) -> int:
    """Fetch unread emails, look up cases, and send replies.

    Returns the number of emails successfully processed.
    """
    emails = email_client.get_unread_emails()
    if not emails:
        logger.info("No new unread emails")
        return 0

    processed = 0
    for email in emails:
        sender_email = email["sender_email"]
        sender_name = email["sender_name"]
        subject = email["subject"]
        msg_id = email["id"]

        logger.info(
            "Processing email from %s <%s> — Subject: %s",
            sender_name,
            sender_email,
            subject,
        )

        # Skip automated/no-reply senders to avoid reply loops
        skip_patterns = [
            "noreply", "no-reply", "donotreply", "do-not-reply",
            "mailer-daemon", "postmaster",
        ]
        if any(p in sender_email.lower() for p in skip_patterns):
            logger.info("Skipping automated sender: %s", sender_email)
            email_client.mark_as_read(msg_id)
            continue

        # Skip if the sender is our own monitored email (avoid self-reply loop)
        if sender_email.lower() == Config.MONITORED_EMAIL.lower():
            logger.info("Skipping email from self: %s", sender_email)
            email_client.mark_as_read(msg_id)
            continue

        # Look up case info in Filevine
        try:
            case_info = scraper.lookup_case(sender_email)
        except Exception:
            logger.exception("Filevine lookup failed for %s", sender_email)
            case_info = None

        # Build and send the response
        reply_html = build_response(sender_name, case_info)

        try:
            email_client.send_reply(msg_id, reply_html)
            email_client.mark_as_read(msg_id)
            processed += 1
            logger.info("Successfully replied to %s", sender_email)
        except Exception:
            logger.exception("Failed to send reply to %s", sender_email)

    return processed


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def run_once():
    """Run a single cycle of email processing."""
    email_client = EmailClient()
    scraper = FilevineScraper()
    count = process_emails(email_client, scraper)
    logger.info("Processed %d emails in this cycle", count)
    return count


def run_polling():
    """Run the polling loop that checks for emails at a regular interval."""
    logger.info(
        "Starting MEDS Email Responder — polling every %d seconds",
        Config.POLL_INTERVAL_SECONDS,
    )
    logger.info("Monitoring mailbox: %s", Config.MONITORED_EMAIL)

    email_client = EmailClient()
    scraper = FilevineScraper()

    while _running:
        try:
            count = process_emails(email_client, scraper)
            logger.info(
                "Cycle complete — processed %d emails. Next check in %ds.",
                count,
                Config.POLL_INTERVAL_SECONDS,
            )
        except Exception:
            logger.exception("Error during email processing cycle")

        # Sleep in small increments so we can respond to shutdown signals
        elapsed = 0
        while _running and elapsed < Config.POLL_INTERVAL_SECONDS:
            time.sleep(1)
            elapsed += 1

    logger.info("MEDS Email Responder stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="MEDS Email Auto-Responder — monitors a mailbox and replies with case info."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single processing cycle and exit (instead of continuous polling).",
    )
    args = parser.parse_args()

    # Validate configuration
    missing = Config.validate()
    if missing:
        logger.error("Missing required configuration: %s", ", ".join(missing))
        logger.error("Copy .env.example to .env and fill in the values.")
        sys.exit(1)

    if args.once:
        run_once()
    else:
        run_polling()


if __name__ == "__main__":
    main()
