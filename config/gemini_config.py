import os
from typing import Optional
from dotenv import load_dotenv


def load_environment() -> None:
    """Loads environment variables from root .env file if present."""
    load_dotenv(override=False)


def get_gemini_api_key() -> str:
    """Retrieves the Gemini API key from environment variables after loading .env.

    Raises:
        ValueError: If GEMINI_API_KEY environment variable is missing or empty.
    """
    load_environment()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not api_key.strip():
        raise ValueError(
            "GEMINI_API_KEY environment variable is not set. "
            "Please set GEMINI_API_KEY in your environment or .env file."
        )
    return api_key.strip()


def is_api_key_available() -> bool:
    """Safely checks if GEMINI_API_KEY is available without exposing key content."""
    load_environment()
    key = os.getenv("GEMINI_API_KEY")
    return bool(key and key.strip())
