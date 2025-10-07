

from pydantic import BaseModel, Field, EmailStr

class UserLogin(BaseModel):
    user_email: EmailStr
    user_password: str = Field(min_length=8, max_length=30)

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"

class TokenRefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    user_email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=30)