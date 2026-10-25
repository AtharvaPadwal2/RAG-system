import psycopg
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: SecretStr
    groq_api_key: SecretStr
    groq_model: str = "openai/gpt-oss-20b"
    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_model: str = "openrouter/free"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


def check_connection():
    settings = Settings()

    with psycopg.connect(
        settings.database_url.get_secret_value(),
        sslmode="require",
        connect_timeout=10,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT extversion FROM pg_extension "
                "WHERE extname = 'vector'"
            )
            result = cursor.fetchone()

    print("Supabase connected successfully.")
    print("pgvector version:", result[0] if result else "Not enabled")


if __name__ == "__main__":
    try:
        check_connection()
    except Exception:
        print(
            "Connection failed. Check your .env connection string, "
            "password, and network connection."
        )
        raise SystemExit(1)