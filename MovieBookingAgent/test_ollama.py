
import requests

url = "http://localhost:11434/api/chat"

data = {
    "model": "llama3.2:1b",
    "messages": [
        {
            "role": "user",
            "content": "Explain a movie booking AI agent in simple English."
        }
    ],
    "stream": False
}

response = requests.post(url, json=data, timeout=120)

if response.status_code == 200:
    result = response.json()
    print("\nCINEVERSE LOCAL AI RESPONSE:\n")
    print(result["message"]["content"])
else:
    print("Error:", response.status_code)
    print(response.text)
