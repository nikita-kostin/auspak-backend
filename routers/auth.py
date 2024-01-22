from fastapi import status, APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from dependencies import get_current_user
from models import supabase, User, Settings


router = APIRouter(prefix="/auth", tags=["auth"])

# Define the OAuth2 scheme for authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# Define the endpoint for user registration
# TODO: implement proper authentication
# TODO: (optional) forbid creating admin accounts from here
@router.post("/register")
def register(user: User):
    email = user.email
    response = supabase.table("users").select("*").eq("email", email).execute()
    if response.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )
    # TODO Hash the user password
    user_dict = user.dict(exclude={"entity", "id"})
    # Insert the user data into the user table
    response = (
        supabase.table("users")
        .insert([{"entity": user.entity.value, **user_dict}])
        .execute()
    )
    # Check if the response has data
    if response.data:
        return {"id": response.data[0]["id"]}
    else:
        # Raise an exception if the registration failed
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed",
        )


# Define the endpoint for user login
# TODO: implement proper authentication
@router.post("/login")
# def login(form_data: OAuth2PasswordRequestForm = Depends()):
def login(email: str, password: str):
    # Get the email and password from the form data
    # email = form_data.email
    # password = form_data.password
    # Query the user table with the email and password
    response = (
        supabase.table("users")
        .select("*")
        .eq("email", email)
        .eq("password", password)
        .execute()
    )
    # Check if the response has data
    if response.data:
        # Generate a token for the user
        token = email  # You should use a proper token generation function here
        # Update the user table with the token
        supabase.table("users").update({"token": token}).eq(
            "id", response.data[0]["id"]
        ).execute()
        # Return the token
        return {"access_token": token, "token_type": "bearer"}
    else:
        # Raise an exception if the login failed
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )


# # Define the endpoint for updating settings
@router.put("/settings")
def update_settings(settings: Settings, current_user: User = Depends(get_current_user)):
    # supabase.table("settings").update(settings.model_dump()).eq("id", response.data[0]["id"]).execute()
    settings_dict = settings.dict(exclude_unset=True)
    supabase.table("users").update(settings_dict).eq("id", current_user.id).execute()
    # Return the updated settings
    return settings


@router.put("/change_password")
def update_password(password: str, current_user: User = Depends(get_current_user)):
    supabase.table("users").update({"password": password}).eq("id", current_user.id).execute()
    # Return the updated settings
    return {"status": "success"}


@router.get("/settings")
def get_settings(current: User = Depends(get_current_user)):
    response = supabase.table("users").select("*").eq("id", current.id).execute()
    if response.data:
        return Settings(**response.data[0])
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return current_user
