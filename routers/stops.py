from fastapi import status, APIRouter, HTTPException, Depends

from dependencies import get_current_user
from models import supabase, Stop, User, UserEntity

router = APIRouter(prefix="/stops", tags=["stops"])

# Define the endpoint for creating a stop
@router.post("/stop")
def create_stop(stop : Stop, current_user: User = Depends(get_current_user)):
    # Check if the current user is a passenger or a parcel operator
    if current_user.entity == UserEntity.passenger or current_user.entity == UserEntity.parcel_operator:
        if stop.bus_id is None:
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
                    # TODO: can optionally add more complex logic here
                    nearest_bus_id = response.data[0]["bus_id"]
                else:
                    # No buses: try next closest stop
                    continue
                # TODO: increase afterwards
                if nearest_stop_distance < 10:
                    # return existing stop id
                    return {"stop_id": nearest_stop["id"], "name" : nearest_stop["name"], "bus_id" : nearest_bus_id}
                else:
                    stop.bus_id = nearest_bus_id
                    break
            if stop.bus_id is None:
                # Raise an exception if the stop is not possible
                # TODO: change to another status code, e.g., 2xx
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Stop creation is not possible: no bus lines nearby",
                )
        # Insert the stop data into the stop table
        response = supabase.rpc('create_stop', {"bus_id": stop.bus_id, "entity" : stop.entity.value, "lat": stop.lat, "long": stop.long, "name" : stop.name}).execute()
        # Check if the response has data
        if response.data:
            # Return the stop id
            # Can also return bus id if needed
            return {"stop_id": response.data[0]["id"], "name" : stop.name, "bus_id": stop.bus_id}
        else:
            # Raise an exception if the stop creation failed
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stop creation failed",
            )
    else:
        # Raise an exception if the current user is not a passenger
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only passengers or parcel operators can create stops",
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
def get_stops_sorted(lat: float = 0, long: float = 0):
    response = supabase.rpc('nearby_stops', {"lat": lat, "long": long}).execute()
    return {"stops": response.data}


@router.get("/stops_in_range")
def get_stops_in_range(min_lat: float = 0, min_long: float = 0, max_lat: float = 0, max_long: float = 0):
    response = supabase.rpc('stops_in_range', {"min_lat": min_lat, "min_long": min_long, "max_lat": max_lat, "max_long": max_long}).execute()
    return {"stops": response.data}
