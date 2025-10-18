from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    URL_DATABASE_SQL:str
    URL_DATABASE_REDIS: str
    KEY_SECRET:str
    ACCESS_TOKEN_EXPIRE_MINUTES:int
    ALGORITHM:str
    BREVO_API_KEY:str
    BREVO_SENDER_EMAIL:str
    CARBON_EMISSION_FACTOR_KG_PER_KWH:float
    GEMINIS_API_KEY:str
    DISCORD_WEBHOOK_URL:str
    FIREBASE_CREDENTIALS_PATH:str


    model_config = {"env_file":".env"}


settings = Settings()
