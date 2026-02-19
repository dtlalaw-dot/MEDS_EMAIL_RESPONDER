# MEDS Email Auto-Responder

Automatically responds to incoming emails on a monitored Microsoft 365 mailbox with case status information pulled from Filevine.

## How It Works

1. **Polls** a Microsoft 365 mailbox for unread emails (every 2 minutes by default)
2. **Looks up** the sender's email address in Filevine to find their associated case
3. **Replies** with a professional email containing the case phase/status
4. **Marks** the email as read so it won't be processed again

If no case is found in Filevine, a generic acknowledgment email is sent instead.

## Architecture

```
main.py              → Polling loop and CLI entry point
email_client.py      → Microsoft Graph API (read/send/mark-read)
filevine_scraper.py  → Playwright browser automation for Filevine
responder.py         → HTML email response builder (Jinja2 templates)
config.py            → Environment-based configuration
```

## Prerequisites

- Python 3.11+
- A Microsoft 365 account with an Azure AD app registration
- Filevine login credentials
- A machine with a browser (Chromium, installed by Playwright)

## Setup

### 1. Clone and install dependencies

```bash
cd MEDS_EMAIL_RESPONDER
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows
pip install -r requirements.txt
playwright install chromium
```

### 2. Azure AD App Registration (for Microsoft 365 email access)

1. Go to [Azure Portal](https://portal.azure.com) → Azure Active Directory → App Registrations → New Registration
2. Name it (e.g., "MEDS Email Responder"), select "Accounts in this organizational directory only"
3. Under **API Permissions**, add:
   - `Microsoft Graph` → Application permissions:
     - `Mail.ReadWrite`
     - `Mail.Send`
4. Click **Grant admin consent**
5. Under **Certificates & secrets**, create a new client secret
6. Note your **Application (client) ID**, **Directory (tenant) ID**, and the **client secret value**

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in:
- `MS_CLIENT_ID` — Azure app client ID
- `MS_CLIENT_SECRET` — Azure app client secret
- `MS_TENANT_ID` — Azure directory (tenant) ID
- `MONITORED_EMAIL` — The mailbox to monitor (e.g., `intake@yourfirm.com`)
- `FILEVINE_USERNAME` — Your Filevine login email
- `FILEVINE_PASSWORD` — Your Filevine login password
- `FIRM_NAME`, `FIRM_PHONE`, `FIRM_EMAIL` — Used in the auto-response

### 4. Run

**Continuous polling (recommended):**
```bash
python main.py
```

**Single run (process once and exit):**
```bash
python main.py --once
```

## Configuration Reference

| Variable | Description | Default |
|---|---|---|
| `MS_CLIENT_ID` | Azure AD application client ID | (required) |
| `MS_CLIENT_SECRET` | Azure AD client secret | (required) |
| `MS_TENANT_ID` | Azure AD tenant ID | (required) |
| `MONITORED_EMAIL` | Email address to monitor | (required) |
| `FILEVINE_URL` | Filevine base URL | `https://app.filevine.com` |
| `FILEVINE_USERNAME` | Filevine login username | (required) |
| `FILEVINE_PASSWORD` | Filevine login password | (required) |
| `POLL_INTERVAL_SECONDS` | Seconds between email checks | `120` |
| `FIRM_NAME` | Firm name in auto-responses | `Our Law Firm` |
| `FIRM_PHONE` | Phone number in auto-responses | (optional) |
| `FIRM_EMAIL` | Email in auto-responses | (optional) |

## Safety Features

- Skips `noreply` / `no-reply` / `mailer-daemon` senders to avoid reply loops
- Skips emails from the monitored address itself (self-reply protection)
- Marks processed emails as read immediately after replying
- Saves Filevine session to avoid re-logging in every cycle
- Graceful shutdown on SIGINT/SIGTERM

## Customizing the Response Template

Edit the Jinja2 templates in `responder.py`:
- `CASE_FOUND_TEMPLATE` — used when a case is found in Filevine
- `NO_CASE_TEMPLATE` — used when no case is found

## Notes

- The Filevine scraper uses headless Chromium via Playwright. The CSS selectors may need adjustment based on your Filevine account's UI version. If case lookups aren't working, run with `headless=False` in `filevine_scraper.py` to debug visually.
- The first run will take longer as Playwright downloads Chromium and the initial Filevine login occurs.
