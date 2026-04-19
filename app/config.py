from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    hospital_api_base_url: str = "https://hospital-directory.onrender.com"
    max_csv_hospitals: int = 20
    request_timeout: float = 30.0


settings = Settings()
