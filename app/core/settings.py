from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    URL_DATABASE_SQL:str
    KEY_SECRET:str
    ACCESS_TOKEN_EXPIRE_MINUTES:int
    ALGORITHM:str


    model_config = {"env_file":".env"}


settings = Settings()
