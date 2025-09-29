from sqlalchemy.orm import Session
from fastapi import APIRouter, HTTPException, Depends, status

from database import get_db
from schemas import UserLogin
from services import authenticate_user_service
from core import create_token_access

router = APIRouter(prefix="/auth",tags=["Authentication"])

@router.post("/login")
def login(user_data:UserLogin | None = None, db:Session = Depends(get_db)):

    user = authenticate_user_service(db,user_data)

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials",headers={"WWW-Authenticate":"Bearer"})

    token_data = {
        "user_id":user.user_id,
        "user_email":user.user_email
    } 

    access_token = create_token_access(data=token_data)

    return{
        "access_token":access_token,
        "token_type":"Bearer"
    }


