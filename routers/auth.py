from fastapi import status, APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from dependencies import get_current_user
from models import supabase, User, UserEntity


router = APIRouter(prefix="/auth", tags=["auth"])

# Define the OAuth2 scheme for authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# Define the endpoint for user registration
# TODO: implement proper authentication
# TODO: (optional) forbid creating admin accounts from here
@router.post("/register")
def register(username: str, password: str, entity: UserEntity):
    response = supabase.table("users").select("*").eq("username", username).execute()
    if response.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this username already exists"
        )
    # Hash the user password
    hashed_password = password  # You should use a proper hashing function here
    # Insert the user data into the user table
    response = supabase.table("users").insert([{
        "username": username,
        "password": hashed_password,
        "entity": entity.value
    }]).execute()
    # Check if the response has data
    if response.data:
        return response.data[0]["id"]
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
def login(username: str, password: str):
    # Get the username and password from the form data
    # username = form_data.username
    # password = form_data.password
    # Query the user table with the username and password
    response = supabase.table("users").select("*").eq("username", username).eq("password", password).execute()
    # Check if the response has data
    if response.data:
        # Generate a token for the user
        token = username  # You should use a proper token generation function here
        # Update the user table with the token
        supabase.table("users").update({"token": token}).eq("id", response.data[0]["id"]).execute()
        # Return the token
        return {"access_token": token, "token_type": "bearer"}
    else:
        # Raise an exception if the login failed
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return current_user
