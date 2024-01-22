from fastapi import status, APIRouter, HTTPException, Depends
from typing import Any, Dict, Iterable

from dependencies import get_current_user
from models import supabase, Stop, User, UserEntity, StopEntity
from routers.bus import update_route, bus_routes
from routers.algorithm import tsp_algorithm


router = APIRouter(prefix="/stops", tags=["stops"])


PASSENGER_STOP_ENTITIES = [StopEntity.passenger_pickup]
MANAGER_STOP_ENTITIES = [StopEntity.static, StopEntity.parcel_pickup, StopEntity.parcel_dropoff]


def check_permissions(user: User, stop: Stop) -> None:
    if stop.entity in PASSENGER_STOP_ENTITIES and user.entity != UserEntity.passenger:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only passengers can create stops of type ${stop.entity.value}"
        )

    if stop.entity in MANAGER_STOP_ENTITIES and user.entity != UserEntity.manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only parcel operators can create stops of type ${stop.entity.value}"
        )


def verify_request(stop: Stop) -> None:
    if stop.entity == StopEntity.static and stop.bus_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Static stops must specify a bus"
        )


def get_active_stops(user: User) -> Iterable[Stop]:
    return supabase.table("stops") \
        .select("*") \
        .eq("user_id", user.id) \
        .eq("is_active", True) \
        .execute()\
        .data


def supabase_create_stop(user: User, stop: Stop) -> Dict[str, Any]:
    # Insert the stop data into the stop table
    response = supabase.rpc('create_stop', {"bus_id": stop.bus_id,
                                            "entity": stop.entity.value,
                                            "lat": stop.lat,
                                            "long": stop.long,
                                            "name": stop.name,
                                            "user_id": user.id}).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stop creation failed",
        )

    update_route(stop.bus_id, response.data[0]["stop_id"])

    return {"bus_id": stop.bus_id, **response.data[0]}


def handle_dynamic_stop(user: User, stop: Stop) -> Dict[str, Any]:
    nearest_stops = get_stops_sorted(lat=stop.lat, long=stop.long)["stops"]
    for nearest_stop in nearest_stops:
        nearest_stop_distance = nearest_stop["dist_meters"]
        if nearest_stop_distance > 1000:
            break

        nearest_bus_id = get_nearest_bus_id(nearest_stop)
        if nearest_bus_id is None:
            # No buses: try next closest stop
            continue

        # Reuse existing stop if found nearby
        if nearest_stop_distance < 10:
            return {"bus_id": nearest_bus_id, **nearest_stop}

        stop.bus_id = nearest_bus_id
        return supabase_create_stop(user, stop)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Stop creation is not possible: no bus lines nearby",
    )


# Define the endpoint for creating a stop
@router.post("/")
def create_stop(stop: Stop, current_user: User = Depends(get_current_user)):
    # Check if user is allowed to execute the request
    check_permissions(current_user, stop)
    # Check if this request contains all the necessary parameters
    verify_request(stop)

    # TODO: (optional) if the static stop already exists, only insert new bus mapping

    # Raise an exception if another stop already exists for a passenger
    if current_user.entity == UserEntity.passenger and get_active_stops(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Passengers can only request one stop at a time",
        )

    if stop.entity != StopEntity.static:
        return handle_dynamic_stop(current_user, stop)

    return supabase_create_stop(current_user, stop)


def get_nearest_bus_id(nearest_stop):
    nearest_stop_id = nearest_stop["id"]
    response = supabase.table("bus_stop_mappings").select("bus_id").eq("stop_id", nearest_stop_id).execute()
    # Check if response has data
    if response.data:
        # Take the bus line that comes first in the table
        # TODO: (optional) add more complex logic here
        return response.data[0]["bus_id"]
    else:
        return None


# Define the endpoint for listing all active stops
@router.get("/list")
def list_stops(current_user: User = Depends(get_current_user)):
    if current_user.entity == UserEntity.manager:
        busesList = supabase.table("buses")\
            .select("*")\
            .eq("is_active", True)\
            .execute().data
        stopsList = supabase.table("stops")\
            .select("*")\
            .eq("is_active", True)\
            .in_("entity", ["parcel_pickup", "parcel_dropoff"])\
            .execute().data
    else:
        if current_user.entity == UserEntity.driver:
            busesList = supabase.table("buses")\
                .select("*")\
                .eq("is_active", True)\
                .eq("driver_id", current_user.id).execute().data
            if not busesList:
                return {"buses": [], "stops": []}
            bus_id = busesList[0]["bus_id"]
        else:
            # passenger
            busIdList = supabase.rpc('bus_for_passenger', {"p_user_id": current_user.id}).execute().data
            if not busIdList:
                return {"buses": [], "stops": []}
            bus_id = busIdList[0]["bus_id"]
            busesList = supabase.table("buses")\
                .select("*")\
                .eq("is_active", True)\
                .eq("bus_id", bus_id).execute().data
            if not busesList:
                return {"buses": [{"bus_id": bus_id, "lat": 0, "long": 0}], "stops": []}
        if bus_id not in bus_routes:
            bus_routes[bus_id] = tsp_algorithm(bus_id=bus_id)["stops"]
        stopsList = bus_routes[bus_id]
    return {"buses": busesList, "stops": stopsList}


# TODO doesn't need to be an endpoint, only used inside create_stop
@router.get("/stops_sorted")
def get_stops_sorted(_: User = Depends(get_current_user), lat: float = 0, long: float = 0):
    response = supabase.rpc('nearby_stops', {"lat_position": lat, "long_position": long}).execute()
    return {"stops": response.data}


@router.get("/stops_in_range")
def get_stops_in_range(
        _: User = Depends(get_current_user),
        min_lat: float = 0,
        min_long: float = 0,
        max_lat: float = 0,
        max_long: float = 0
):
    response = supabase\
        .rpc(
            'stops_in_range',
            {"min_lat": min_lat, "min_long": min_long, "max_lat": max_lat, "max_long": max_long}
        )\
        .execute()
    return {"stops": response.data}
