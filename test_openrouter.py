from openai import OpenAI

from database import Settings

settings = Settings()

try:
    with OpenAI(
        api_key=settings.openrouter_api_key.get_secret_value(),
        base_url="https://openrouter.ai/api/v1",
        timeout=30.0,
        max_retries=0,
    ) as client:
        response = client.chat.completions.create(
            model=settings.openrouter_model,
            messages=[
                {
                    "role": "user",
                    "content": "Explain a knight fork in one sentence.",
                }
            ],
            max_tokens=512,
        )

    print("Model:", response.model)
    print("Answer:", response.choices[0].message.content)

except Exception as error:
    print("OpenRouter test failed:", type(error).__name__)
    print("HTTP status:", getattr(error, "status_code", None))