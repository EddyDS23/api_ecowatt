
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from fastapi import HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from app.core import settings

# El oauth2_schema no cambia
oauth2_schema = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

class TokenData(BaseModel):
    user_id: int | None = None

# 1. Renombramos la función para que sea más genérica
def create_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Si no se especifica, le damos una expiración por defecto de 15 min
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.KEY_SECRET, algorithm=settings.ALGORITHM)
    return encoded_jwt

# 2. Modificamos get_current_user para que solo contenga el user_id
# Esto es más seguro y eficiente, ya que el ID es lo único que necesitas para identificar al usuario.
async def get_current_user(token: str = Depends(oauth2_schema)) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    not_authenticated_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise not_authenticated_exception

    try:
        payload = jwt.decode(token, settings.KEY_SECRET, algorithms=[settings.ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
        
        token_data = TokenData(user_id=user_id)
    except JWTError:
        raise credentials_exception
    
    return token_data