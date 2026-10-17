"""Runtime configuration, read from environment variables with safe defaults.

Kept intentionally tiny (no extra dependencies) for the hackathon POC.
"""
import os


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    # Origins allowed by CORS (the Vite dev server runs on 5173).
    cors_origins: list[str] = _split(
        os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    )

    # Nominatim (OpenStreetMap) geocoding endpoint used by the /api/geocode proxy.
    nominatim_url: str = os.getenv(
        "NOMINATIM_URL", "https://nominatim.openstreetmap.org/search"
    )
    # Nominatim's usage policy requires a descriptive User-Agent.
    nominatim_user_agent: str = os.getenv(
        "NOMINATIM_USER_AGENT", "WarsawOpenData/0.1 (hackathon POC)"
    )


settings = Settings()
