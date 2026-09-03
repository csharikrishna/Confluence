import os
import requests
from dotenv import load_dotenv

load_dotenv()

invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
stream = False

api_key = os.getenv("NVIDIA_API_KEY")
headers = {
    "Authorization": f"Bearer {api_key}",
    "Accept": "text/event-stream" if stream else "application/json",
}

payload = {
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "What is in this image?"
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "https://assets.ngc.nvidia.com/products/api-catalog/phi-3-5-vision/example1b.jpg"
          }
        }
      ]
    }
  ],
  "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
  "max_tokens": 65536,
  "reasoning_budget": 16384,
  "stream": stream,
  "temperature": 0.6,
  "top_p": 0.95
}

response = requests.post(invoke_url, headers=headers, json=payload, stream=stream)
if stream:
    for line in response.iter_lines():
        if line:
            print(line.decode("utf-8"))
else:
    print(response.json())