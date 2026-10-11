import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client()

print("Fetching available models for your API key...")
try:
    for model in client.models.list():
        print(model.name)
except Exception as e:
    print(f"Error connecting: {e}")
