from fastapi import status, HTTPException

from models import supabase, User


# Define a helper function to get the current user from the token
# def get_current_user(token: str = Depends(oauth2_scheme)):
def get_current_user(token: str):
    # Query the user table with the token
    response = supabase.table("users").select("*").eq("token", token).execute()
    # Check if the response has data
    if response.data:
        # Return the user as a User object
        return User(**response.data[0])
    else:
        # Raise an exception if the token is invalid
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
