from fastapi import status, APIRouter, Depends, HTTPException

from dependencies import get_current_user
from models import supabase, User


router = APIRouter(prefix="/legacy/settings", tags=["settings"])


#TODO LEGACY CODE

# Define the endpoint for updating settings
# @router.put("/")
# def update_settings(settings: Settings, current_user: User = Depends(get_current_user)):
#     # Check if the settings user id matches the current user id
#     if settings.user_id == current_user.id:
#         # Query the settings table with the user id
#         response = supabase.table("settings").select("*").eq("user_id", settings.user_id).execute()
#         # Check if the response has data
#         if response.data:
#             # Update the settings table with the new settings
#             supabase.table("settings").update(settings.model_dump()).eq("id", response.data[0]["id"]).execute()
#             # Return the updated settings
#             return settings
#         else:
#             # Insert the settings data into the settings table
#             supabase.table("settings").insert([settings.model_dump()]).execute()
#             # Return the inserted settings
#             return settings
#     else:
#         # Raise an exception if the settings user id does not match the current user id
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Settings user id does not match current user id",
#         )


# # Define the endpoint for getting settings
# @router.get("/")
# def get_settings(current_user: User = Depends(get_current_user)) -> Settings:
#     # Query the settings table with the current user id
#     response = supabase.table("settings").select("*").eq("user_id", current_user.id).execute()
#     # Check if the response has data
#     if response.data:
#         # Return the settings as a Settings object
#         return Settings(**response.data[0])
#     else:
#         # Return an empty Settings object with the current user id
#         return Settings(id=0, user_id=current_user.id)
