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

    cookie_secure: bool = False # При True передача только через HTTPS

    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = False
    smtp_from: str = "Магазин <no-reply@shop.local>"
    app_base_url: str = "http://localhost:8000"

    # Без extra=ignore строго требует все поля из файла окружения
    model_config = SettingsConfigDict(env_file='.env')

settings = Settings()
