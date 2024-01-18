from fastapi import status, APIRouter, HTTPException, Depends

from dependencies import get_current_user
from models import supabase, Stop, User, UserEntity, StopEntity
from routers.algorithm import tsp_algorithm

router = APIRouter(prefix="/bus", tags=["bus"])

# Cached bus routes
# TODO reverse list after full path completed
bus_routes = dict()

# TODO insert new stops into supabase

@router.post("/start")
def start_bus(current_user: User = Depends(get_current_user), bus_id : int = 0):
    if current_user.entity != UserEntity.driver:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can start the bus",
        )
    # TODO check if driver is in another bus
    # TODO check if another driver is in the bus
    if bus_id not in bus_routes:
        bus_routes[bus_id] = tsp_algorithm(bus_id=bus_id)["stops"]
    response = supabase.table("buses").insert([{
        "bus_id": bus_id,
        "driver_id": current_user.id,
        "stop_number": 0 # bus_routes[bus_id][0]["id"]
    }]).execute()
    if response.data:
        return {"stops" : [stop["name"] for stop in bus_routes[bus_id]]}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bus instantiation failed",
        )
    

# TODO router get bus lines

    
