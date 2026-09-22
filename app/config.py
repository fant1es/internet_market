from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    postgres_user: str
    postgres_password: str
    postgres_db: str

    secret_key: str
    algorithm: str
    access_token_expire_minutes: int

    # Без extra=ignore строго требует все поля из файла окружения
    model_config = SettingsConfigDict(env_file='.env')

settings = Settings()
