"""Filevine browser automation for looking up case information."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError as PwTimeout
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

from config import Config

logger = logging.getLogger(__name__)

STORAGE_DIR = Path("playwright-storage")
STORAGE_FILE = STORAGE_DIR / "filevine-session.json"


@dataclass
class CaseInfo:
    """Holds case/project information retrieved from Filevine."""
    project_name: str = ""
    phase: str = ""
    case_number: str = ""
    client_name: str = ""
    found: bool = False
    projects: list[dict] = field(default_factory=list)

    def summary(self) -> str:
        """Human-readable summary for the email response."""
        if not self.found:
            return ""
        lines = []
        if self.project_name:
            lines.append(f"Case: {self.project_name}")
        if self.case_number:
            lines.append(f"Case Number: {self.case_number}")
        if self.phase:
            lines.append(f"Current Phase: {self.phase}")
        return "\n".join(lines)


class FilevineScraper:
    """Automates Filevine web UI to look up case information by contact email."""

    def __init__(self):
        self._browser: Browser | None = None
        self._page: Page | None = None
        STORAGE_DIR.mkdir(exist_ok=True)

    def _launch_browser(self, pw) -> Browser:
        return pw.chromium.launch(headless=True)

    def _login(self, page: Page) -> bool:
        """Log into Filevine. Returns True on success."""
        logger.info("Logging into Filevine at %s", Config.FILEVINE_URL)
        page.goto(Config.FILEVINE_URL, wait_until="networkidle", timeout=60000)

        # Wait for the login form to appear
        try:
            # Filevine uses a standard username/password form
            # The selectors may need adjustment based on Filevine's current UI
            page.wait_for_selector(
                'input[type="email"], input[name="username"], input[name="loginfmt"], #username',
                timeout=15000,
            )
        except PwTimeout:
            # Might already be logged in if session was saved
            if "app.filevine" in page.url and "/login" not in page.url.lower():
                logger.info("Already logged in via saved session")
                return True
            logger.error("Could not find login form")
            return False

        # Fill in credentials
        email_input = page.query_selector(
            'input[type="email"], input[name="username"], input[name="loginfmt"], #username'
        )
        if email_input:
            email_input.fill(Config.FILEVINE_USERNAME)

        # Some login flows have a "Next" button before password
        next_btn = page.query_selector(
            'button[type="submit"], input[type="submit"], #next, .next-button'
        )
        if next_btn:
            next_btn.click()
            page.wait_for_timeout(2000)

        # Fill password
        try:
            password_input = page.wait_for_selector(
                'input[type="password"], input[name="password"], #password',
                timeout=10000,
            )
            if password_input:
                password_input.fill(Config.FILEVINE_PASSWORD)
        except PwTimeout:
            logger.error("Could not find password field")
            return False

        # Submit login
        submit_btn = page.query_selector(
            'button[type="submit"], input[type="submit"], #loginButton, .login-button'
        )
        if submit_btn:
            submit_btn.click()

        # Wait for navigation after login
        try:
            page.wait_for_url("**/app.filevine**", timeout=30000)
            logger.info("Successfully logged into Filevine")

            # Save session for reuse
            page.context.storage_state(path=str(STORAGE_FILE))
            return True
        except PwTimeout:
            logger.error("Login did not redirect to Filevine app")
            return False

    def _search_contact_by_email(self, page: Page, email: str) -> CaseInfo:
        """Search for a contact in Filevine by email and get associated project info."""
        case_info = CaseInfo()

        # Navigate to the contacts/address book page
        contacts_url = f"{Config.FILEVINE_URL}/contacts"
        logger.info("Navigating to contacts page: %s", contacts_url)
        page.goto(contacts_url, wait_until="networkidle", timeout=30000)

        # Use Filevine's contact search
        try:
            search_input = page.wait_for_selector(
                'input[placeholder*="Search"], input[type="search"], .search-input, '
                '[data-testid="search-input"], input[aria-label*="search" i]',
                timeout=15000,
            )
            if search_input:
                search_input.fill(email)
                page.keyboard.press("Enter")
                page.wait_for_timeout(3000)  # Wait for search results
        except PwTimeout:
            logger.warning("Could not find contact search input, trying URL-based search")
            # Try URL-based search as fallback
            page.goto(
                f"{Config.FILEVINE_URL}/contacts?search={email}",
                wait_until="networkidle",
                timeout=30000,
            )
            page.wait_for_timeout(3000)

        # Look for contact results and click the first match
        contact_links = page.query_selector_all(
            'a[href*="/contact/"], .contact-row, .contact-item, '
            'tr[data-testid*="contact"], .contact-result'
        )

        if not contact_links:
            logger.info("No contacts found for email: %s", email)
            return case_info

        # Click the first matching contact
        contact_links[0].click()
        page.wait_for_timeout(3000)

        # Look for the contact's name
        name_el = page.query_selector(
            '.contact-name, h1, h2, [data-testid="contact-name"]'
        )
        if name_el:
            case_info.client_name = name_el.inner_text().strip()

        # Navigate to Associated Projects tab/section
        assoc_tab = page.query_selector(
            'a:has-text("Associated Projects"), button:has-text("Associated Projects"), '
            '[data-testid*="associated"], .tab:has-text("Projects")'
        )
        if assoc_tab:
            assoc_tab.click()
            page.wait_for_timeout(3000)

        # Extract project/case information
        project_rows = page.query_selector_all(
            '.project-row, .project-item, tr[data-testid*="project"], '
            'a[href*="/project/"], .associated-project'
        )

        if project_rows:
            # Click the first (most recent) project to get details
            project_rows[0].click()
            page.wait_for_timeout(3000)

            case_info.found = True
            case_info = self._extract_project_details(page, case_info)
        else:
            # Try extracting info from the current page if projects are displayed inline
            case_info = self._try_inline_project_extraction(page, case_info)

        return case_info

    def _extract_project_details(self, page: Page, case_info: CaseInfo) -> CaseInfo:
        """Extract project phase and status from a project detail page."""
        # Extract project name from the page header
        project_name = page.query_selector(
            '.project-name, .project-title, h1, h2, '
            '[data-testid="project-name"], .matter-name'
        )
        if project_name:
            case_info.project_name = project_name.inner_text().strip()

        # Extract phase/status - Filevine shows phase in a badge or status area
        phase_el = page.query_selector(
            '.phase-name, .phase-badge, .project-phase, [data-testid="phase"], '
            '.status-badge, .phase-label, .phase, .project-status'
        )
        if phase_el:
            case_info.phase = phase_el.inner_text().strip()

        # Try getting case number from the URL or page content
        current_url = page.url
        if "/project/" in current_url:
            parts = current_url.split("/project/")
            if len(parts) > 1:
                case_info.case_number = parts[1].split("/")[0].split("?")[0]

        # If phase wasn't found via selector, try the vitals/sidebar area
        if not case_info.phase:
            vitals = page.query_selector_all(
                '.vital-item, .vitals-section .vital, [data-testid*="vital"]'
            )
            for vital in vitals:
                text = vital.inner_text().lower()
                if "phase" in text or "status" in text:
                    case_info.phase = vital.inner_text().strip()
                    break

        logger.info(
            "Extracted project details - Name: %s, Phase: %s",
            case_info.project_name,
            case_info.phase,
        )
        return case_info

    def _try_inline_project_extraction(self, page: Page, case_info: CaseInfo) -> CaseInfo:
        """Try to extract project info if displayed inline on the contact page."""
        # Some Filevine layouts show project info in a flyout or inline list
        project_info = page.query_selector_all(
            '.project-info, .case-info, [data-testid*="project"]'
        )
        for info_el in project_info:
            text = info_el.inner_text()
            if text.strip():
                case_info.found = True
                case_info.project_name = text.strip().split("\n")[0]
                break
        return case_info

    def lookup_case(self, sender_email: str) -> CaseInfo:
        """Look up case information in Filevine for the given sender email.

        This is the main public method. It handles browser lifecycle.
        """
        logger.info("Looking up case in Filevine for: %s", sender_email)
        case_info = CaseInfo()

        if not HAS_PLAYWRIGHT:
            logger.warning("Playwright not installed — skipping Filevine lookup")
            return case_info

        try:
            with sync_playwright() as pw:
                browser = self._launch_browser(pw)

                # Try to reuse saved session
                context_args = {}
                if STORAGE_FILE.exists():
                    context_args["storage_state"] = str(STORAGE_FILE)

                context = browser.new_context(**context_args)
                page = context.new_page()

                # Check if session is still valid, login if needed
                page.goto(Config.FILEVINE_URL, wait_until="networkidle", timeout=60000)
                if "/login" in page.url.lower() or "identity" in page.url.lower():
                    if not self._login(page):
                        logger.error("Failed to log into Filevine")
                        return case_info

                case_info = self._search_contact_by_email(page, sender_email)

                # Save session state for next time
                context.storage_state(path=str(STORAGE_FILE))
                browser.close()

        except Exception:
            logger.exception("Error during Filevine lookup for %s", sender_email)

        return case_info
