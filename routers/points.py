from fastapi import APIRouter, Depends

from dependencies import get_current_user
from models import supabase, User


router = APIRouter(prefix="/points", tags=["points"])


@router.get("/")
def get_points_sorted(current_user: User = Depends(get_current_user), lat: float = 0, long: float = 0):
    response = supabase.rpc('nearby_points', {"lat": lat, "long": long}).execute()
    return {"points": response.data}


@router.get("/{point_id}")
def get_point(current_user: User = Depends(get_current_user), p_id: int = 0):
    response = supabase.rpc('get_points', {"p_id": p_id}).execute()
    return {"point": response.data}


#TODO: debug this endpoint
# @app.put("/points/{point_id}")
# def get_point(current_user: User = Depends(get_current_user), loc_id: int = 0, name: str = "", lat: float = 0, long: float = 0):
#     response = supabase.rpc('update_points', {"point_id": loc_id, "p_name": name, "lat": lat, "long": long}).execute()
#     return {"point": response.data}

@router.post("/")
def create_point(current_user: User = Depends(get_current_user), loc_id: int = 0, name: str = "", lat: float = 0, long: float = 0):
    response = supabase.rpc('create_points', {"id": loc_id, "name": name, "lat": lat, "long": long}).execute()
    return {"point": response.data}


@router.get("/in_range")
def get_points_in_range(current_user: User = Depends(get_current_user), min_lat: float = 0, min_long: float = 0, max_lat: float = 0, max_long: float = 0):
    response = supabase.rpc('points_in_range', {"min_lat": min_lat, "min_long": min_long, "max_lat": max_lat, "max_long": max_long}).execute()
    return {"points": response.data}
