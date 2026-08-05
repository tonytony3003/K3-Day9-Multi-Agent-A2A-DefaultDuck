"""
LLM Client Module
==================
Wrapper for Groq REST API using stdlib urllib (no pip install needed).
Model: llama-3.1-8b-instant (8B parameters, within the ≤10B requirement).
"""

import json
import time
import urllib.request
import urllib.error
from typing import Any

# Model name declared explicitly in source code (per assignment requirement)
MODEL_NAME = "llama-3.1-8b-instant"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Rate limiting: Groq free tier = 30 RPM for gemma2-9b-it
MIN_REQUEST_INTERVAL = 2.1  # seconds between requests (safe margin)


class GroqLLMClient:
    """Client for calling Groq API with Gemma 2 9B model."""

    def __init__(self, api_key: str):
        if not api_key or api_key == "your_groq_api_key_here":
            raise ValueError(
                "GROQ_API_KEY not set. Please add your key to .env file.\n"
                "Get a free key at: https://console.groq.com/keys"
            )
        self.api_key = api_key
        self.model = MODEL_NAME
        self._last_request_time = 0.0
        self.total_calls = 0
        self.total_tokens = 0

    def call(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        json_mode: bool = True,
    ) -> str:
        """
        Call Groq API and return the response text.

        Args:
            system_prompt: System instruction for the LLM
            user_prompt: User message containing data to analyze
            temperature: Sampling temperature (0 = deterministic)
            max_tokens: Maximum response length
            json_mode: If True, request JSON response format

        Returns:
            The LLM response text (should be valid JSON if json_mode=True)
        """
        # Rate limiting
        self._wait_for_rate_limit()

        # Build request body
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        data = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(
            GROQ_API_URL,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MultiAgentDisputeResolver/1.0",
            },
            method="POST",
        )

        # Retry logic with exponential backoff
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=60) as response:
                    result = json.loads(response.read().decode("utf-8"))

                self._last_request_time = time.time()
                self.total_calls += 1

                # Track token usage
                usage = result.get("usage", {})
                self.total_tokens += usage.get("total_tokens", 0)

                # Extract response text
                content = result["choices"][0]["message"]["content"]
                return content

            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8") if e.fp else ""
                if e.code == 429:
                    # Rate limited - wait and retry
                    wait = (attempt + 1) * 5
                    print(f"    [LLM] Rate limited. Waiting {wait}s...")
                    time.sleep(wait)
                    continue
                elif e.code == 503:
                    # Service unavailable - retry
                    wait = (attempt + 1) * 3
                    print(f"    [LLM] Service unavailable. Retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                else:
                    raise RuntimeError(
                        f"Groq API error {e.code}: {error_body}"
                    ) from e
            except urllib.error.URLError as e:
                if attempt < max_retries - 1:
                    wait = (attempt + 1) * 3
                    print(f"    [LLM] Connection error. Retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"Failed to connect to Groq API: {e}") from e

        raise RuntimeError("Max retries exceeded for Groq API call")

    def call_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> dict:
        """
        Call Groq API and parse the response as JSON.

        Returns:
            Parsed JSON dict from LLM response.
        """
        response_text = self.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(response_text[start:end])
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"LLM returned invalid JSON: {response_text[:200]}")

    def _wait_for_rate_limit(self):
        """Wait if needed to respect Groq rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            sleep_time = MIN_REQUEST_INTERVAL - elapsed
            time.sleep(sleep_time)
