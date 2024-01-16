from fastapi import status, APIRouter, HTTPException, Depends

from dependencies import get_current_user
from models import supabase, Stop, User, UserEntity




router = APIRouter(prefix="/stops", tags=["stops"])

#TODO please check the logic here
#TODO while creating a stop as an operator, I get a bad request error but stop is still created
# Define the endpoint for creating a stop
@router.post("/stop")
def create_stop(long: str, lat: str, current_user: User = Depends(get_current_user)):
    # Check if the current user is a passenger or a parcel operator
    if current_user.entity == UserEntity.passenger or current_user.entity == UserEntity.parcel_operator:
        if current_user.entity == UserEntity.passenger:
            # Check if the passenger already requested a stop
            # Query the stop table with user id
            response = supabase.table("stops").select("*").eq("user_id", current_user.id).execute()
            # Check if response has data
            if response.data:
                # Raise an exception if the stop is not possible
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Passengers can only request one stop at a time",
                )
        # Dummy driver selection: first driver in the table
        # Query the user table to get all drivers
        response = supabase.table("users").select("id").eq("entity", UserEntity.driver.value).execute()
        # Check if response has data
        if response.data:
            driver_id = response.data[0]["id"]
        else:
            # Raise an exception if the stop is not possible
            # TODO: change to another status code, e.g., 2xx
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Creating a stop is not possible",
            )
        # Insert the stop data into the stop table
        response = supabase.rpc('create_stop', {"lat": lat, "long": long, "driver_id": driver_id, "user_id": current_user.id}).execute()
        # Check if the response has data
        if response.data:
            # Return the stop id
            return {"stop_id": response.data[0]["id"]}
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


# Define the endpoint for listing stops
@router.get("/stops")
def list_stops(current_user: User = Depends(get_current_user)):
    # Query the stop table with the current user id
    response = supabase.table("stops").select("*").eq("user_id", current_user.id).execute()
    # Check if the response has data
    if response.data:
        # Return the list of stops as Stop objects
        return [Stop(**stop) for stop in response.data]
    else:
        # Return an empty list if no stops are found
        return []

#TODO does not depend on the user
@router.get("/stops_sorted")
def get_stops_sorted(current_user: User = Depends(get_current_user), lat: float = 0, long: float = 0):
    response = supabase.rpc('nearby_stops', {"lat": lat, "long": long}).execute()
    return {"stops": response.data}


#TODO does not depend on the user
@router.get("/stops_in_range")
def get_stops_in_range(current_user: User = Depends(get_current_user), min_lat: float = 0, min_long: float = 0, max_lat: float = 0, max_long: float = 0):
    response = supabase.rpc('stops_in_range', {"min_lat": min_lat, "min_long": min_long, "max_lat": max_lat, "max_long": max_long}).execute()
    return {"stops": response.data}