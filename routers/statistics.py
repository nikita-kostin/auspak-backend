from fastapi import APIRouter, Depends, HTTPException, status
from dependencies import get_current_user
from models import User, supabase, UserEntity

router = APIRouter(prefix="/statistics", tags=["statistics"])


# Define the endpoint for getting statistics
@router.get("/")
def get_statistics(current_user: User = Depends(get_current_user)):
    if current_user.entity != UserEntity.manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parcel operators can get statistics",
        )
        # TODO len, but must be count to avoid loading all data
    statistics = {
        "parcels_delivered": len(
            supabase.table("stops")
            .select("*")
            .eq("is_active", False)
            .in_("entity", ["parcel_pickup", "parcel_dropoff"])
            .execute()
            .data
        ),  # parcels + passangers
        "parcels_pending": len(
            supabase.table("stops")
            .select("*")
            .eq("is_active", True)
            .in_("entity", ["parcel_pickup", "parcel_dropoff"])
            .execute()
            .data
        ),
        "peak_hours": "11:43",
        "passenger_transported": len(
            supabase.table("stops")
            .select("*")
            .eq("is_active", False)
            .eq("entity", "passenger_pickup")
            .execute()
            .data
        ),
        "passenger_transit": len(
            supabase.table("stops")
            .select("*")
            .eq("is_active", True)
            .eq("entity", "passenger_pickup")
            .execute()
            .data
        ),
        "capacity_utilization": 80.8,
        "emissions": 0.129,
        "customer_retention": 73.4,
        "parcels_damage": 0.13,
    }
    return {"data": statistics}


@router.get("/events")
def get_events(current_user: User = Depends(get_current_user)):
    if current_user.entity != UserEntity.manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parcel operators can get statistics",
        )
    # TODO equal to parcel_status
    events = (
        supabase.table("stops")
        .select("*")
        .eq("is_active", False)
        .in_("entity", ["parcel_pickup", "parcel_dropoff"])
        .execute()
        .data
    )

    # Filter the events to include only stop_id, lat, long, and updated_at
    # Get a list of stop_ids from the events
    stop_ids = [event["stop_id"] for event in events]

    # Find all corresponding entries in the bus_stop_mappings_table
    bus_stop_mappings = (
        supabase.table("bus_stop_mappings")
        .select("*")
        .in_("stop_id", stop_ids)
        .execute()
        .data
    )

    # Create a dictionary to map stop_id to bus_stop_mapping
    stop_id_to_mapping = {mapping["stop_id"]: mapping for mapping in bus_stop_mappings}

    # Filter the events to include only stop_id, lat, long, updated_at, and the corresponding bus_stop_mapping
    filtered_events = [
        {
            "stop_id": event["stop_id"],
            "lat": event["lat"],
            "long": event["long"],
            "updated_at": event["updated_at"],
            "entity": event["entity"],
            "bus_stop_mapping": stop_id_to_mapping.get(event["stop_id"])["bus_id"],
        }
        for event in events
    ]

    return {"data": filtered_events}
