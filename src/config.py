import os
from dotenv import load_dotenv
from src.secrets import get_secret

# Load GOOGLE_API_KEY from .env using python-dotenv
load_dotenv()

GOOGLE_API_KEY = get_secret("GOOGLE_API_KEY")

if not GOOGLE_API_KEY or GOOGLE_API_KEY.strip() == "" or GOOGLE_API_KEY == "your_key_here":
    raise EnvironmentError(
        'GOOGLE_API_KEY is missing. In Streamlit Cloud secrets, add GOOGLE_API_KEY = "your_key_here".\n'
        "For local runs, add GOOGLE_API_KEY=your_key_here to .env."
    )

from crewai import LLM
llm = LLM(
    model="gemini/gemini-3.1-flash-lite",
    api_key=GOOGLE_API_KEY,
    temperature=0.3
)

import google.generativeai as genai
genai.configure(api_key=GOOGLE_API_KEY)
gemini_model = genai.GenerativeModel("gemini-3.1-flash-lite")
