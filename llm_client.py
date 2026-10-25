from groq import (
    Groq,
    APIConnectionError as GroqConnectionError,
    APIStatusError as GroqStatusError,
)
from openai import OpenAI

from database import Settings


def generate_answer(messages: list[dict[str, str]]) -> str:
    settings = Settings()

    try:
        with Groq(
            api_key=settings.groq_api_key.get_secret_value(),
            timeout=30.0,
            max_retries=0,
        ) as client:
            response = client.chat.completions.create(
                model=settings.groq_model,
                messages=messages,
                max_completion_tokens=1024,
            )

        answer = response.choices[0].message.content

        if not answer or not answer.strip():
            raise RuntimeError("Groq returned no answer text.")

        return answer.strip()

    except GroqStatusError as error:
        # Retry through another provider only for temporary failures.
        if error.status_code != 429 and error.status_code < 500:
            raise

    except GroqConnectionError:
        # Includes connection failures and SDK timeout errors.
        pass

    fallback_key = settings.openrouter_api_key.get_secret_value()

    if not fallback_key:
        raise RuntimeError("Fallback provider is not configured.")

    with OpenAI(
        api_key=fallback_key,
        base_url="https://openrouter.ai/api/v1",
        timeout=30.0,
        max_retries=0,
    ) as client:
        response = client.chat.completions.create(
            model=settings.openrouter_model,
            messages=messages,
            max_tokens=1024,
        )

    answer = response.choices[0].message.content

    if not answer or not answer.strip():
        raise RuntimeError("OpenRouter returned no answer text.")

    return answer.strip()