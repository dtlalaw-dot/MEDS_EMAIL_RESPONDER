"""Configuration management for the MEDS Email Responder."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    # Microsoft 365 / Graph API
    MS_CLIENT_ID: str = os.getenv("MS_CLIENT_ID", "")
    MS_CLIENT_SECRET: str = os.getenv("MS_CLIENT_SECRET", "")
    MS_TENANT_ID: str = os.getenv("MS_TENANT_ID", "")
    MONITORED_EMAIL: str = os.getenv("MONITORED_EMAIL", "")

    # Filevine
    FILEVINE_URL: str = os.getenv("FILEVINE_URL", "https://app.filevine.com")
    FILEVINE_USERNAME: str = os.getenv("FILEVINE_USERNAME", "")
    FILEVINE_PASSWORD: str = os.getenv("FILEVINE_PASSWORD", "")

    # Polling
    POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", "120"))

    # Firm info for responses
    FIRM_NAME: str = os.getenv("FIRM_NAME", "Our Law Firm")
    FIRM_PHONE: str = os.getenv("FIRM_PHONE", "")
    FIRM_EMAIL: str = os.getenv("FIRM_EMAIL", "")

    # Graph API scopes and endpoints
    GRAPH_API_BASE: str = "https://graph.microsoft.com/v1.0"
    GRAPH_SCOPES: list = ["https://graph.microsoft.com/.default"]

    @classmethod
    def validate(cls) -> list[str]:
        """Return a list of missing required configuration fields."""
        required = {
            "MS_CLIENT_ID": cls.MS_CLIENT_ID,
            "MS_CLIENT_SECRET": cls.MS_CLIENT_SECRET,
            "MS_TENANT_ID": cls.MS_TENANT_ID,
            "MONITORED_EMAIL": cls.MONITORED_EMAIL,
            "FILEVINE_USERNAME": cls.FILEVINE_USERNAME,
            "FILEVINE_PASSWORD": cls.FILEVINE_PASSWORD,
        }
        return [key for key, value in required.items() if not value]
