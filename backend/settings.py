from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Оставляем только типы. Сами секреты Pydantic автоматически подтянет из .env!
    bot_token: str
    kie_api_key: str
    shop_id: str
    secret_key: str

    # Несекретные настройки можно оставить с дефолтными значениями
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/nanobanana"
    start_balance: int = 5
    cost_nanobanana: int = 1
    cost_nanobanana_2: int = 3
    cost_nanobanana_pro: int = 4

    # Указываем, откуда брать секреты, и разрешаем игнорировать лишнее
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
