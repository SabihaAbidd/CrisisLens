import os
from dotenv import load_dotenv

# Load GOOGLE_API_KEY from .env using python-dotenv
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY or GOOGLE_API_KEY.strip() == "" or GOOGLE_API_KEY == "your_key_here":
    raise EnvironmentError(
        "GOOGLE_API_KEY is missing. Add it to your .env file.\n"
        "Get a free key at aistudio.google.com"
    )

from langchain_google_genai import ChatGoogleGenerativeAI
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro",
    google_api_key=GOOGLE_API_KEY,
    temperature=0.3
)

import google.generativeai as genai
genai.configure(api_key=GOOGLE_API_KEY)
gemini_model = genai.GenerativeModel("gemini-1.5-pro")
