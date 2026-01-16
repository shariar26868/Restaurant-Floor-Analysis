from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # -------------------------------------------------
    # MongoDB
    # -------------------------------------------------
    MONGODB_URL: str
    DATABASE_NAME: str = "resturant_table"

    # -------------------------------------------------
    # AWS S3
    # -------------------------------------------------
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "restaurant-videos"

    # -------------------------------------------------
    # OpenAI
    # -------------------------------------------------
    OPENAI_API_KEY: str

    class Config:
        env_file = ".env"
        extra = "ignore"   # extra env vars থাকলেও error দেবে না


settings = Settings()
