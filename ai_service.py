import os
import json
from openai import OpenAI

def get_ai_category_suggestion(description: str, available_categories: list[str]) -> str:
    """Uses OpenAI to predict the best category based on user expense description."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return ""

    client = OpenAI(api_key=api_key)

    prompt = f"""
    Given the following expense description: "{description}"
    Choose the most relevant category from this exact list: {available_categories}.
    Return ONLY a JSON object in this format: {{"category": "Selected Category Name"}}
    If no category fits, pick the closest one.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        data = json.loads(response.choices[0].message.content)
        return data.get("category", "")
    except Exception:
        return ""