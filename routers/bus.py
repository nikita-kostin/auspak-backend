from fastapi import status, APIRouter, HTTPException, Depends

from dependencies import get_current_user
from models import supabase, User, UserEntity, StopEntity
from routers.algorithm import tsp_algorithm

router = APIRouter(prefix="/bus", tags=["bus"])

# TODO reconstruct route on new stop creation
# Cached bus routes
bus_routes = dict()
# Cached results of build_next_stops
build_next_stops_cache = dict()


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
        "stop_number": 0,
        "lat": bus_routes[bus_id][0]["lat"],
        "long": bus_routes[bus_id][0]["long"]
    }]).execute()
    if response.data:
        return build_next_stops(bus_id, cached=False)
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
    return {"data": response.data}


@router.post("/next")
def move_to_next_stop(current_user: User = Depends(get_current_user)):
    # Implicit check whether user is a driver and has active buses
    response = supabase.table("buses")\
        .select("*")\
        .eq("driver_id", current_user.id)\
        .eq("is_active", True)\
        .execute()
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active buses associated with the user",
        )
    bus = response.data[0]
    row_id = bus["id"]
    bus_id = bus["bus_id"]
    direction = bus["direction"]
    current_stop_i = bus["stop_number"]
    if bus_id not in bus_routes:
        # returns route for True order
        bus_routes[bus_id] = tsp_algorithm(bus_id=bus_id)["stops"]
        if not direction:
            bus_routes[bus_id].reverse()
    bus_route = bus_routes[bus_id]
    current_stop = bus_route[current_stop_i]
    if current_stop["entity"] != StopEntity.static.value:
        response = supabase.table("stops").update({"is_active": False}).eq("stop_id", current_stop["stop_id"]).execute()
        del bus_route[current_stop_i]
        next_stop_i = current_stop_i
    else:
        next_stop_i = current_stop_i + 1
    update_dict = dict()
    if next_stop_i == len(bus_route):
        next_stop_i = (next_stop_i + 1) % len(bus_route)
        bus_route.reverse()
        update_dict["direction"] = not direction
    update_dict["stop_number"] = next_stop_i
    update_dict["lat"] = bus_route[next_stop_i]["lat"]
    update_dict["long"] = bus_route[next_stop_i]["long"]
    response = supabase.table("buses").update(update_dict).eq("id", row_id).execute()
    return build_next_stops(bus_id, current_stop_i=next_stop_i, cached=False)


def update_route(bus_id: int, stop_id: int):
    response = supabase.table("buses")\
        .select("*")\
        .eq("bus_id", bus_id)\
        .eq("is_active", True)\
        .execute()
    if not response.data:
        # No active buses
        return
    bus = response.data[0]
    row_id = bus["id"]
    bus_id = bus["bus_id"]
    direction = bus["direction"]
    current_stop_i = bus["stop_number"]
    # Returns route for True order
    bus_routes[bus_id] = tsp_algorithm(bus_id=bus_id)["stops"]
    if not direction:
        bus_routes[bus_id].reverse()
    if current_stop_i >= find_stop_index_by_id(bus_routes[bus_id], stop_id):
        response = supabase.table("buses").update({"stop_number": current_stop_i + 1}).eq("id", row_id).execute()
    return


def find_stop_index_by_id(stops, stop_id):
    for index, item in enumerate(stops):
        if item.get("stop_id") == stop_id:
            return index
    return None


@router.get("/list_stops")
def list_next_stops(current_user: User = Depends(get_current_user), num_next_stops: int = 3):
    """
    Lists current stop and next N stops

    Parameters:
    - token (str): The user token.
    - num_next_stops (str): Number of next stops listed.

    Returns:
    {
        "bus_id": int,
        "current_stop": dict,
        "next_stops": list[dict]
    }
    """
    if current_user.entity != UserEntity.driver:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a driver",
        )
    response = supabase.table("buses")\
        .select("*")\
        .eq("driver_id", current_user.id)\
        .eq("is_active", True)\
        .execute()
    if not response.data:
        return {"bus_id": None, "current_stop": None, "next_stops": None}
    bus = response.data[0]
    bus_id = bus["bus_id"]
    if bus_id not in bus_routes:
        # returns route for True order
        bus_routes[bus_id] = tsp_algorithm(bus_id=bus_id)["stops"]
        if not bus["direction"]:
            bus_routes[bus_id].reverse()
    return build_next_stops(bus_id=bus_id, current_stop_i=bus["stop_number"], num_next_stops=num_next_stops)


def build_next_stops(bus_id: int, current_stop_i: int = 0, num_next_stops: int = 3, cached: bool = True):
    if cached and (bus_id in build_next_stops_cache):
        return build_next_stops_cache[bus_id]
    bus_route = bus_routes[bus_id].copy()
    next_stops = list()
    for _ in range(num_next_stops + 1):
        next_stops.append(bus_route[current_stop_i])
        if bus_route[current_stop_i]["entity"] != StopEntity.static.value:
            del bus_route[current_stop_i]
        else:
            current_stop_i += 1
        if current_stop_i == len(bus_route):
            bus_route.reverse()
            # bus_route must contain at least one static stop
            current_stop_i = 1 % len(bus_route)
    result = {"bus_id": bus_id, "current_stop": next_stops[0], "next_stops": next_stops[1:]}
    build_next_stops_cache[bus_id] = result
    return result


# # List users that requested stop of this bus
# @router.get("/users")
# def list_users(current_user: User = Depends(get_current_user), query: str = "", entity: UserEntity = None):
#     if current_user.entity != UserEntity.driver:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Only drivers can view user list",
#         )
#     if entity == UserEntity.driver:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Can't chat with drivers",
#         )
#     users = supabase.rpc('get_users_for_driver', {"p_driver_id": current_user.id}).execute().data
#     if query != "":
#         users = [user for user in users if filter_user(user, query)]
#     if entity is not None:
#         users = [user for user in users if user["entity"] == entity.value]
#     return {"users": users}


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
    # Fetch all active bus_ids from buses
    response = supabase.table("buses").select("bus_id").eq("is_active", True).execute()
    bus_ids_in_buses = [item["bus_id"] for item in response.data]
    # Find bus_ids that are in mappings but not in active buses
    bus_ids_not_in_buses = [bus_id for bus_id in bus_ids_in_mappings if bus_id not in bus_ids_in_buses]
    bus_ids_not_in_buses.sort
    return {"lines": set(bus_ids_not_in_buses)}
