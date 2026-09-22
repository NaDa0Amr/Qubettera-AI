import os
import requests

# API_KEY = os.environ["OPENROUTER_API_KEY"]
API_KEY = "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"

URL = "https://openrouter.ai/api/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

# model = "google/gemma-4-26b-a4b-it:free"
model = "dots-studio/dots-3-note-preview:free"

# --------------------------------------------------
# First API call
# --------------------------------------------------

messages = [
    {
        "role": "user",
        "content": "Hi. How are you? Can you explain the basic idea of dynamic physics?"
    }
]

response = requests.post(
    URL,
    headers=headers,
    json={
        "model": model,
        "messages": messages,
        "reasoning": {
            "enabled": True
        }
    }
)

print("Status:", response.status_code)
print("Response:", response.text)

data = response.json()
