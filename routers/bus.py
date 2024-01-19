from fastapi import status, APIRouter, HTTPException, Depends

from dependencies import get_current_user
from models import supabase, Stop, User, UserEntity, StopEntity
from routers.algorithm import tsp_algorithm

router = APIRouter(prefix="/bus", tags=["bus"])

# Cached bus routes
# TODO reverse list after full path completed
bus_routes = dict()

# TODO bus position update

@router.post("/start")
def start_bus(current_user: User = Depends(get_current_user), bus_id: int = 0):
    if current_user.entity != UserEntity.driver:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can start the bus",
        )
    response = supabase.rpc('check_availability', {"p_driver_id": current_user.id, "p_bus_id": bus_id}).execute()
    if response.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bus or driver are already busy",
        )
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


@router.post("/stop")
def stop_bus(current_user: User = Depends(get_current_user)):
    # Set is_active to False
    # Implicit check whether user is a driver and has active buses
    response = supabase.table("buses").update({"is_active": False}).eq("driver_id", current_user.id).execute()
    return {response}


# List users that requested stop of this bus
@router.get("/users")
def list_users(current_user: User = Depends(get_current_user), query: str = "", entity: UserEntity = None):
    if current_user.entity != UserEntity.driver:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can view user list",
        )
    if entity == UserEntity.driver:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can't chat with drivers",
        )
    users = supabase.rpc('get_users_for_driver', {"driver_id_": current_user.id}).execute().data
    if query != "":
        users = [user for user in users if \
            user["first_name"].startswith(query) or
            user["last_name"].startswith(query) or
            (user["last_name"] + user["last_name"]).startswith(query)]
        
    if entity is not None:
        users = [user for user in users if user["entity"] == entity.value]
    return {"users": users}

# List bus lines that are not taken by any driver
@router.get("/lines")
def list_bus_lines(current_user: User = Depends(get_current_user)):
    if current_user.entity != UserEntity.driver:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can view bus lines list",
        )
    # Fetch all bus_ids from bus_stop_mappings
    response = supabase.from_("bus_stop_mappings").select("bus_id").execute()
    bus_ids_in_mappings = [item["bus_id"] for item in response.data]
    # Fetch all bus_ids from buses
    response = supabase.from_("buses").select("bus_id").execute()
    bus_ids_in_buses = [item["bus_id"] for item in response.data]
    # Find bus_ids that are in mappings but not in buses
    bus_ids_not_in_buses = [bus_id for bus_id in bus_ids_in_mappings if bus_id not in bus_ids_in_buses]
    bus_ids_in_buses.sort
    return {"buses" : set(bus_ids_not_in_buses)}
