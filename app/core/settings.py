from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    URL_DATABASE_SQL:str
    KEY_SECRET:str
    ACCESS_TOKEN_EXPIRE_MINUTES:int
    ALGORITHM:str
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_STARTTLS: bool
    MAIL_SSL_TLS: bool


    model_config = {"env_file":".env"}


settings = Settings()
