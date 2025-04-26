import requests
import json
from pprint import pprint

# Define the URL and the payload
url = 'http://localhost:11434/api/generate'
payload = {
    "model": "llama2",
    "prompt": "Why is the sky blue?",
    "system_role": "sales expert with 50 years of experience",
    "stream": False
}

# Convert the payload to a JSON string
data = json.dumps(payload)

# Make the POST request
response = requests.post(url, data=data, headers={'Content-Type': 'application/json'})
print(response.text)

data = response.json()
pprint(data)