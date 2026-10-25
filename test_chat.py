from groq import Groq

from database import Settings

settings = Settings()

client = Groq(
    api_key=settings.groq_api_key.get_secret_value(),
    timeout=30.0,
    max_retries=0,
)

try:
    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {
                "role": "system",
                "content": "You are a chess tutor. Explain concepts simply.",
            },
            {
                "role": "user",
                "content": "Explain a knight fork in two sentences.",
            },
        ],
        max_completion_tokens=512,
    )

    answer = response.choices[0].message.content
    print(answer or "The model returned no answer text.")

except Exception as error:
    print("Chat request failed. Error type:", type(error).__name__)