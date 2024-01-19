from fastapi import status, APIRouter, HTTPException, Depends

from dependencies import get_current_user
from models import supabase, User, UserEntity
from routers.algorithm import tsp_algorithm

router = APIRouter(prefix="/bus", tags=["bus"])

# Cached bus routes
# TODO reverse list after full path completed
# TODO reconstruct route on new stop creation
bus_routes = dict()


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
        "stop_number": 0    # bus_routes[bus_id][0]["id"]
    }]).execute()
    if response.data:
        return get_next_stops(bus_id)
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


@router.post("/next")
def move_to_next_stop(current_user: User = Depends(get_current_user)):
    # Implicit check whether user is a driver and has active buses
    response = supabase.table("buses")\
        .select("*")\
        .eq("driver_id", current_user.id)\
        .eq("is_active", True).execute().data
    if not response:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No buses associated with the user",
        )
    row_id = response["id"]
    bus_id = response["bus_id"]
    direction = response["direction"]
    current_stop = response["stop_number"]
    if bus_id not in bus_routes:
        # returns route for True order
        bus_routes[bus_id] = tsp_algorithm(bus_id=bus_id)["stops"]
        if direction:
            bus_routes[bus_id].reverse()
    current_stop = (current_stop + 1) % len(bus_routes[bus_id])
    update_dict = {"stop_number" : current_stop}
    if current_stop == 0:
        bus_routes[bus_id].reverse()
        update_dict["direction"] = True
    response = supabase.table("buses").update(update_dict).eq("id", row_id).execute()
    return get_next_stops(bus_id, current_stop_index=current_stop)


def get_next_stops(bus_id: int, current_stop_i: int = 0, num_next_stops: int = 3):
    bus_route = bus_routes[bus_id]
    indices = list(range(len(bus_route)))
    result = {"current_stop": bus_route[current_stop_i], "next_stops": list()}
    current_stop_i = (current_stop_i + 1) % len(indices)
    if current_stop_i == 0:
        indices.reverse()
        current_stop_i = (current_stop_i + 1) % len(indices)
    while num_next_stops > 0:
        result["next_stops"].append(bus_route[indices[current_stop_i]])
        current_stop_i = (current_stop_i + 1) % len(indices)
        if current_stop_i == 0:
            indices.reverse()
            current_stop_i = (current_stop_i + 1) % len(indices)
        num_next_stops -= 1
    return result
    

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
    users = supabase.rpc('get_users_for_driver', {"p_driver_id": current_user.id}).execute().data
    if query != "":
        users = [user for user in users if filter_user(user, query)]
    if entity is not None:
        users = [user for user in users if user["entity"] == entity.value]
    return {"users": users}


def filter_user(user: dict, query: str):
    first_last_match = f"{user['first_name']} {user['last_name']}".startswith(query)
    last_first_match = f"{user['last_name']} {user['first_name']}".startswith(query)
    return first_last_match or last_first_match


# List bus lines that are not taken by any driver
@router.get("/lines")
def list_bus_lines(current_user: User = Depends(get_current_user)):
    if current_user.entity != UserEntity.driver:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can view bus lines list",
        )
    # Fetch all bus_ids from bus_stop_mappings
    response = supabase.table("bus_stop_mappings").select("bus_id").execute()
    bus_ids_in_mappings = [item["bus_id"] for item in response.data]
    # Fetch all bus_ids from buses
    response = supabase.table("buses").select("bus_id").execute()
    bus_ids_in_buses = [item["bus_id"] for item in response.data]
    # Find bus_ids that are in mappings but not in buses
    bus_ids_not_in_buses = [bus_id for bus_id in bus_ids_in_mappings if bus_id not in bus_ids_in_buses]
    bus_ids_in_buses.sort
    return {"buses": set(bus_ids_not_in_buses)}
