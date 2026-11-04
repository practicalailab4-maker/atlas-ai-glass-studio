import os
from pathlib import Path

from dotenv import load_dotenv

# Locate the .env file inside the backend folder
ENV_PATH = Path(__file__).resolve().parent / ".env"

# Load environment variables
load_dotenv(dotenv_path=ENV_PATH)

# Read the OpenAI API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")