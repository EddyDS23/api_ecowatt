from sqlalchemy.orm import Session
from fastapi import APIRouter, HTTPException, status, Depends

from database import get_db
from core import TokenData, get_current_user

from schemas import UserResponse, UserCreate, UserUpdate, UserChangePassword
from services import get_user_service,create_user_service, update_user_service, change_password_user_service

router = APIRouter(prefix="/users",tags=["User"])

@router.get("/",response_model=UserResponse)
def get_current_user_route(db:Session = Depends(get_db),current_user:TokenData = Depends(get_current_user)):
    user = get_user_service(db,current_user.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User not found", )
    return user


@router.post("/",response_model=UserResponse)
def create_user_route(user_data:UserCreate,db:Session = Depends(get_db),):
    user = create_user_service(db,user_data)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="User couldnt create")
    return user

@router.patch("/",response_model=UserResponse)
def update_user_route(user_data:UserUpdate, db:Session = Depends(get_db), current_user:TokenData = Depends(get_current_user)):

    user = update_user_service(db,current_user.user_id,user_data)