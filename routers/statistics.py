from fastapi import APIRouter, Depends, HTTPException, status


from dependencies import get_current_user
from models import User, supabase, UserEntity

router = APIRouter(prefix="/statistics", tags=["statistics"])


# Define the endpoint for getting statistics
@router.get("/")
def get_statistics(current_user: User = Depends(get_current_user)):
    if current_user.entity == UserEntity.parcel_operator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parcel operators can get statistics",
        )
        return {"data": {}}
        #TODO len, but must be count to avoid loading all data
    statistics = {
        "parcels_delivered": len(supabase.table("stops").select("*").execute().data),
        "parcels_pending": len(supabase.table("stops").select("*").eq("is_active", True).execute().data),
        "peak_hours": "11:43",
        "revenue_per_parcel": 9,
        "avg_cost_per_parcel": 8,
        "capacity_utilization": 80.8,
        "emissions": 0.129,
        "customer_retention": 73.4,
        "parcels_damage": 0.13
    }    
    return {"data": statistics}
