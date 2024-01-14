from fastapi import APIRouter, Depends

from dependencies import get_current_user
from models import User


router = APIRouter(prefix="/statistics", tags=["statistics"])


# Define the endpoint for getting statistics
@router.get("/")
def get_statistics(current_user: User = Depends(get_current_user)):
    return {"statistics": "TBD"}
