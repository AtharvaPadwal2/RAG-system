from unittest.mock import patch

import httpx
from groq import RateLimitError

from llm_client import generate_answer

request = httpx.Request(
    "POST",
    "https://api.groq.com/openai/v1/chat/completions",
)
response = httpx.Response(429, request=request)

simulated_error = RateLimitError(
    "Simulated rate limit for testing",
    response=response,
    body={"error": {"message": "Simulated rate limit"}},
)

try:
    with patch(
        "llm_client.Groq",
        side_effect=simulated_error,
    ):
        answer = generate_answer(
            [
                {
                    "role": "user",
                    "content": "Explain a knight fork in one sentence.",
                }
            ]
        )

    print("Fallback succeeded.")
    print("Answer:", answer)

except Exception as error:
    print("Fallback test failed:", type(error).__name__)