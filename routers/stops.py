from fastapi import status, APIRouter, HTTPException, Depends

from dependencies import get_current_user
from models import supabase, Stop, User, UserEntity, StopEntity

router = APIRouter(prefix="/stops", tags=["stops"])

# Define the endpoint for creating a stop
@router.post("/")
def create_stop(stop : Stop, current_user: User = Depends(get_current_user)):
    # Check if the current user is a driver
    if current_user.entity == UserEntity.driver:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Drivers can't create stops",
        )
    else:
        if stop.entity == StopEntity.static:
            if stop.bus_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Static stop must specify a bus",
                )
            # TODO: (optional) if the stop already exists, only insert new bus mapping
        else:
            # Reset the bus line if specified and determine it dynamically
            stop.bus_id = None
            nearest_stops = get_stops_sorted(lat=stop.lat, long=stop.long)["stops"]
            for nearest_stop in nearest_stops:
                nearest_stop_distance = nearest_stop["dist_meters"]
                if nearest_stop_distance > 1000:
                    break
                nearest_stop_id = nearest_stop["id"]
                response = supabase.table("bus_stop_mappings").select("bus_id").eq("stop_id", nearest_stop_id).execute()
                # Check if response has data
                if response.data:
                    # Take the bus line that comes first in the table
                    # TODO: (optional) add more complex logic here
                    nearest_bus_id = response.data[0]["bus_id"]
                else:
                    # No buses: try next closest stop
                    continue
                # TODO: increase afterwards
                if nearest_stop_distance < 10:
                    # Return existing stop info
                    return {"bus_id" : nearest_bus_id, **nearest_stop}
                else:
                    stop.bus_id = nearest_bus_id
                    break
            if stop.bus_id is None:
                # Raise an exception if the stop is not possible
                # TODO: (optional) change to another status code, e.g., 2xx
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Stop creation is not possible: no bus lines nearby",
                )
        # Insert the stop data into the stop table
        response = supabase.rpc('create_stop', {"bus_id": stop.bus_id,
                                                "entity" : stop.entity.value,
                                                "lat": stop.lat,
                                                "long": stop.long,
                                                "name" : stop.name}).execute()
        # Check if the response has data
        if response.data:
            # Return the stop info
            return {"bus_id": stop.bus_id, **response.data[0]}
        else:
            # Raise an exception if the stop creation failed
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stop creation failed",
            )

# Define the endpoint for listing all stops
@router.get("/stops")
def list_stops(current_user: User = Depends(get_current_user)):
    # Query the stop table with the current user id
    response = supabase.table("stops").select("*").execute()
    # Check if the response has data
    if response.data:
        # Return the list of stops as Stop objects
        return [Stop(**stop) for stop in response.data]
    else:
        # Return an empty list if no stops are found
        return []

#TODO doesn't need to be an endpoint, only used inside create_stop
@router.get("/stops_sorted")
def get_stops_sorted(current_user: User = Depends(get_current_user), lat: float = 0, long: float = 0):
    response = supabase.rpc('nearby_stops', {"lat_position": lat, "long_position": long}).execute()
    return {"stops": response.data}


@router.get("/stops_in_range")
def get_stops_in_range(current_user: User = Depends(get_current_user), min_lat: float = 0, min_long: float = 0, max_lat: float = 0, max_long: float = 0):
    response = supabase.rpc('stops_in_range', {"min_lat": min_lat, "min_long": min_long, "max_lat": max_lat, "max_long": max_long}).execute()
    return {"stops": response.data}
