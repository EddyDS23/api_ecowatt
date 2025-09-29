from datetime import datetime, timedelta, timezone


from jose import JWTError,jwt
from fastapi import HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer

from pydantic import BaseModel
from core import settings

oauth2_schema = OAuth2PasswordBearer(tokenUrl="auth/login",auto_error=False)

class TokenData(BaseModel):
    user_email:str | None = None
    user_id:int | None = None

    
def create_token_access(data:dict, expire_delta:timedelta|None=None):
    
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (expire_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))

    to_encode.update({"exp":expire})

    encode_jwt = jwt.encode(to_encode,settings.KEY_SECRET, algorithm=settings.ALGORITHM)
    return encode_jwt

async def  get_current_user(token:str = Depends(oauth2_schema)) -> TokenData:

    token_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Couldnt be validate credentials",headers={"WWW-Authenticate":"Bearer"})

    token_exception_not_authenticate = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticate",headers={"WWW-Authenticate":"Bearer"})

    if token is None:
        raise token_exception_not_authenticate
    

    try:
        payload = jwt.decode(token, settings.KEY_SECRET, algorithms=[settings.ALGORITHM])

        user_id = payload.get("user_id")
        user_email = payload.get("user_email")
        if user_email is None:
            raise token_exception
        
        return TokenData(user_id=user_id,user_email=user_email)
    except JWTError:
        return None