import requests
import json
import os

public_url = "https://cubicle-bottling-opulently.ngrok-free.dev"
llm_model = os.getenv("LLM_MODEL", "gemma4:e4b")

# Define the URL and headers
url = f"{public_url}/api/generate"
headers = {
    "Content-Type": "application/json"
}

# Define the data (payload) to send in the POST request
data = {
    "model": llm_model,
    "prompt": "Hi. How are you? Can you please explain the benefits of plants in homes?",
    "stream": False
}

# Send the POST request
response = requests.post(url, headers=headers, data=json.dumps(data))

# Check if the request was successful and print the response
if response.status_code == 200:
    print("Response:", response.json()["response"])
else:
    print("Failed to get a response. Status code:", response.status_code)
    print(response.text)