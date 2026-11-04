from openai import OpenAI
from backend.config import OPENAI_API_KEY


def get_openai_client():
    """Create an OpenAI client using Atlas's saved API key."""

    if not OPENAI_API_KEY:
        raise RuntimeError("OpenAI API key is not configured.")

    return OpenAI(api_key=OPENAI_API_KEY)