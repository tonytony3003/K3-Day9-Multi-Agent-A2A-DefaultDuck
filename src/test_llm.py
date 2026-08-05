"""Test llama-3.1-8b-instant model on Groq API."""
import sys, os, json, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, ".env")
api_key = ""
with open(env_path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line.startswith("GROQ_API_KEY="):
            api_key = line.split("=", 1)[1].strip()

from llm_client import GroqLLMClient

# Temporarily test with llama-3.1-8b-instant
client = GroqLLMClient(api_key)
client.model = "llama-3.1-8b-instant"

try:
    res = client.call_json(
        system_prompt="You are a helpful assistant. Output JSON.",
        user_prompt='Respond with JSON: {"status": "ok", "model": "llama-3.1-8b-instant"}',
    )
    print("SUCCESS!")
    print(json.dumps(res, indent=2))
except Exception as e:
    print(f"Error: {e}")
