import os

from google import genai

from config import load_api_key


class GeminiClient:
    def __init__(self, model="gemini-3-flash-preview"):
        self.model = model
        key = load_api_key()
        if not os.environ.get("GEMINI_API_KEY"):
            os.environ["GEMINI_API_KEY"] = key
        self.client = genai.Client()

    def generate_text(self, prompt):
        response = self.client.models.generate_content(
            model=self.model, contents=prompt
        )
        return response.text or ""
