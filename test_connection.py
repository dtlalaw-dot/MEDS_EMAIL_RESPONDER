"""Quick test script to verify Microsoft Graph API connection and email access."""

import sys
from config import Config
from email_client import EmailClient


def main():
    print("=" * 60)
    print("MEDS Email Responder — Connection Test")
    print("=" * 60)

    # 1. Check config
    print("\n[1/4] Checking configuration...")
    missing = Config.validate()
    if missing:
        print(f"  FAIL: Missing config: {', '.join(missing)}")
        sys.exit(1)
    print(f"  OK: Client ID: {Config.MS_CLIENT_ID[:8]}...")
    print(f"  OK: Tenant ID: {Config.MS_TENANT_ID[:8]}...")
    print(f"  OK: Monitored email: {Config.MONITORED_EMAIL}")

    # 2. Test authentication
    print("\n[2/4] Testing authentication (token acquisition)...")
    client = EmailClient()
    try:
        token = client._get_token()
        print(f"  OK: Token acquired ({len(token)} chars)")
    except Exception as e:
        print(f"  FAIL: {e}")
        sys.exit(1)

    # 3. Test reading inbox
    print("\n[3/4] Testing inbox access (fetching unread emails)...")
    try:
        emails = client.get_unread_emails()
        print(f"  OK: Found {len(emails)} unread emails")
        for e in emails[:5]:
            print(f"      - From: {e['sender_name']} <{e['sender_email']}>")
            print(f"        Subject: {e['subject']}")
    except Exception as e:
        print(f"  FAIL: {e}")
        sys.exit(1)

    # 4. Test sending (dry run — sends to yourself)
    print("\n[4/4] Testing send capability (sending test email to self)...")
    try:
        import requests
        headers = client._headers()
        url = (
            f"{Config.GRAPH_API_BASE}/users/{Config.MONITORED_EMAIL}"
            f"/sendMail"
        )
        payload = {
            "message": {
                "subject": "MEDS Email Responder — Test Email",
                "body": {
                    "contentType": "HTML",
                    "content": "<p>This is a test email from the MEDS Email Responder. If you received this, the system is working correctly.</p>",
                },
                "toRecipients": [
                    {"emailAddress": {"address": Config.MONITORED_EMAIL}}
                ],
            }
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        print(f"  OK: Test email sent to {Config.MONITORED_EMAIL}")
    except Exception as e:
        print(f"  FAIL: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED — the system is ready to run!")
    print(f"Start with: python main.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
