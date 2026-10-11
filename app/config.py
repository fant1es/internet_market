from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    postgres_user: str
    postgres_password: str
    postgres_db: str

    secret_key: str
    algorithm: str
    access_token_expire_minutes: int

    # Данные для создания администратора через сид
    admin_name: str = "Администратор"
    admin_email: str | None = None
    admin_password: str | None = None

    # Без extra=ignore строго требует все поля из файла окружения
    model_config = SettingsConfigDict(env_file='.env')

settings = Settings()
