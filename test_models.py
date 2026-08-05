import os, requests
from dotenv import load_dotenv
load_dotenv()
models_to_test = [
    "google/gemma-2-9b-it:free",
    "mistralai/mistral-7b-instruct:free",
    "nousresearch/hermes-3-llama-3.1-8b:free",
    "qwen/qwen-2-7b-instruct:free",
    "meta-llama/llama-3-8b-instruct:free"
]
headers = {'Authorization': f"Bearer {os.environ.get('OPENROUTER_API_KEY')}"}
for m in models_to_test:
    data = {
        "model": m,
        "messages": [{"role": "user", "content": "hi"}]
    }
    r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
    print(f"{m}: {r.status_code}")
    if r.status_code == 200:
        print("Success!")
