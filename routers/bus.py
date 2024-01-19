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


@router.post("/stop")
def stop_bus(current_user: User = Depends(get_current_user)):
    # Set is_active to False
    # Implicit check whether user is a driver and has active buses
    response = supabase.table("buses").update({"is_active": False}).eq("driver_id", current_user.id).execute()
    return {response}


# List users that requested stop of this bus
@router.get("/users")
def list_users(current_user: User = Depends(get_current_user)):
    if current_user.entity != UserEntity.driver:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can view user list",
        )
    # Get bus_id associated with the driver_id
    response = supabase.table("buses") \
        .select("bus_id") \
        .eq("is_active", True) \
        .eq("driver_id", current_user.id) \
        .execute()
    # Extract bus_id from the response
    if not response.data:
        return {"users" : []}
    bus_id = response.data[0]["bus_id"]
    # Get stop_ids associated with the bus_id
    response = supabase.table("bus_stop_mappings") \
        .select("stop_id") \
        .eq("bus_id", bus_id) \
        .execute()
    # Extract stop_ids from the inner query result
    stop_ids = [entry["stop_id"] for entry in response.data]
    # Use the extracted stop_ids in the outer query
    response = supabase.table("stops") \
        .select("user_id") \
        .neq("entity", "static") \
        .eq("is_active", True) \
        .in_("stop_id", stop_ids) \
        .execute()
    return {"users" : response.data}

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
