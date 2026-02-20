"""Microsoft Graph API email client for reading and sending emails."""

import logging
from datetime import datetime, timedelta, timezone

import msal
import requests

from config import Config

logger = logging.getLogger(__name__)


class EmailClient:
    """Handles email operations via Microsoft Graph API."""

    def __init__(self):
        self._token: str | None = None
        self._token_expiry: datetime | None = None
        self._app = msal.ConfidentialClientApplication(
            Config.MS_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{Config.MS_TENANT_ID}",
            client_credential=Config.MS_CLIENT_SECRET,
        )

    def _get_token(self) -> str:
        """Acquire or refresh the access token."""
        if self._token and self._token_expiry and datetime.now(timezone.utc) < self._token_expiry:
            return self._token

        result = self._app.acquire_token_for_client(scopes=Config.GRAPH_SCOPES)
        if "access_token" not in result:
            error = result.get("error_description", "Unknown error")
            raise RuntimeError(f"Failed to acquire token: {error}")

        self._token = result["access_token"]
        expires_in = result.get("expires_in", 3600)
        self._token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        logger.info("Acquired new Graph API access token")
        return self._token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }

    def get_unread_emails(self) -> list[dict]:
        """Fetch unread emails from the monitored mailbox.

        Returns a list of email dicts with keys:
            id, subject, sender_email, sender_name, received_at, body_preview
        """
        url = (
            f"{Config.GRAPH_API_BASE}/users/{Config.MONITORED_EMAIL}"
            f"/mailFolders/inbox/messages"
            f"?$filter=isRead eq false"
            f"&$select=id,subject,from,receivedDateTime,bodyPreview"
            f"&$orderby=receivedDateTime desc"
            f"&$top=50"
        )
        resp = requests.get(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()

        emails = []
        for msg in data.get("value", []):
            sender = msg.get("from", {}).get("emailAddress", {})
            emails.append({
                "id": msg["id"],
                "subject": msg.get("subject", "(no subject)"),
                "sender_email": sender.get("address", ""),
                "sender_name": sender.get("name", ""),
                "received_at": msg.get("receivedDateTime", ""),
                "body_preview": msg.get("bodyPreview", ""),
            })

        logger.info("Fetched %d unread emails", len(emails))
        return emails

    def send_reply(self, message_id: str, reply_html: str) -> None:
        """Send a reply to a specific email message.

        Args:
            message_id: The Graph API message ID to reply to.
            reply_html: HTML body content for the reply.
        """
        url = (
            f"{Config.GRAPH_API_BASE}/users/{Config.MONITORED_EMAIL}"
            f"/messages/{message_id}/reply"
        )
        payload = {
            "message": {
                "body": {
                    "contentType": "HTML",
                    "content": reply_html,
                }
            }
        }
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=30)
        resp.raise_for_status()
        logger.info("Sent reply to message %s", message_id)

    def mark_as_read(self, message_id: str) -> None:
        """Mark an email as read so it won't be processed again."""
        url = (
            f"{Config.GRAPH_API_BASE}/users/{Config.MONITORED_EMAIL}"
            f"/messages/{message_id}"
        )
        payload = {"isRead": True}
        resp = requests.patch(url, headers=self._headers(), json=payload, timeout=30)
        resp.raise_for_status()
        logger.debug("Marked message %s as read", message_id)
