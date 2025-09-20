from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    URL_DATABASE_SQL:str

    model_config = {"env_file":".env"}


settings = Settings()
