# Import the required modules
import logging
import os
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from enum import Enum
from supabase import create_client, Client
from typing import Dict, Optional
from fastapi.responses import HTMLResponse

# Create the FastAPI app
app = FastAPI()

# Create the Supabase client
supabase_url = os.environ.get("SUPABASE_URL", None)
supabase_key = os.environ.get("SUPABASE_KEY", None)
supabase: Client = create_client(supabase_url, supabase_key)


# Define the user entities as an Enum
class UserEntity(Enum):
    driver = "driver"
    passenger = "passenger"
    parcel_operator = "parcel_operator"


# Define the user model
class User(BaseModel):
    id: int
    username: str
    password: str
    entity: UserEntity
    token: str


# Define the chat model
class Chat(BaseModel):
    id: int
    driver_id: int
    user_id: int


class Message(BaseModel):
    id: int
    chat_id: int
    sender_id: int
    text: str


# Define the stop model
class Stop(BaseModel):
    id: int
    driver_id: int
    user_id: int
    address: str
    coordinates: str


# Define the settings model
class Settings(BaseModel):
    id: int
    user_id: int
    email: Optional[str] = None
    phone_number: Optional[str] = None
    birthdate: Optional[str] = None


# Define the OAuth2 scheme for authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


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


# Define the endpoint for user registration
# TODO: implement proper authentication
@app.post("/register")
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
@app.post("/login")
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


@app.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return current_user


# Define the endpoint for creating a chat
@app.post("/chat")
def create_chat(user_id: int, current_user: User = Depends(get_current_user)):
    # Check if the current user is a driver
    if current_user.entity == UserEntity.driver:
        # Insert the chat data into the chat table
        response = supabase.table("chats").insert([{
            "driver_id": current_user.id,
            "user_id": user_id
        }]).execute()
        # Check if the response has data
        if response.data:
            # Return the chat id
            return {"chat_id": response.data[0]["id"]}
        else:
            # Raise an exception if the chat creation failed
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chat creation failed",
            )
    else:
        # Raise an exception if the current user is not a driver
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can create chats",
        )


# Define the endpoint for listing chats
@app.get("/chats")
def list_chats(current_user: User = Depends(get_current_user)):
    # Query the chat table with the current user id
    query = supabase.table("chats").select("*")
    query = query.eq("driver_id" if current_user.entity == UserEntity.driver else "user_id", current_user.id)
    response = query.execute()
    # Check if the response has data
    if response.data:
        # Return the list of chats as Chat objects
        return [Chat(**chat) for chat in response.data]
    else:
        # Return an empty list if no chats are found
        return []


class ConnectionHandler(object):

    active_sockets: Dict[int, Dict[int, WebSocket]]

    def __init__(self) -> None:
        self.active_sockets = dict()

    def register(self, chat_id: int, user_id: int, websocket: WebSocket) -> None:
        self.active_sockets.setdefault(chat_id, dict())
        self.active_sockets[chat_id][user_id] = websocket

    async def broadcast(self, chat_id: int, message: Message) -> None:
        for websocket in self.active_sockets[chat_id].values():
            await websocket.send_json(message)

    def close(self, chat_id: int, user_id: int) -> None:
        self.active_sockets.setdefault(chat_id, dict())
        self.active_sockets[chat_id].pop(user_id, None)

connection_handler = ConnectionHandler()

@app.get("/chat/{chat_id}/history")
def get_chat_history(chat_id: int, current_user: User = Depends(get_current_user)):
    response = supabase.table("chats").select("*").eq("id", chat_id).execute()
    if response.data:
        # Get the chat as a Chat object
        chat = Chat(**response.data[0])
        if current_user.id in [chat.driver_id, chat.user_id]:
            response = supabase.table("messages").select("*").eq("chat_id", chat_id).execute()
            return response.data
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not authorised to access the chat",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No chat with given id found",
        )


# Define the websocket endpoint for opening a chat
@app.websocket("/chat/{chat_id}")
async def open_chat(websocket: WebSocket, chat_id: int, current_user: User = Depends(get_current_user)):
    print("entered")
    # Accept the websocket connection
    await websocket.accept()
    # Query the chat table with the chat id
    response = supabase.table("chats").select("*").eq("id", chat_id).execute()
    print(response)
    # Check if the response has data
    if response.data:
        # Get the chat as a Chat object
        chat = Chat(**response.data[0])
        # Check if the current user is either the driver or the user of the chat
        print(current_user.id, chat)
        if current_user.id in [chat.driver_id, chat.user_id]:
            print(f"user {current_user.username} entered the chat")
            connection_handler.register(chat_id, current_user.id, websocket)
            # existing_messages = supabase.table("messages").select("*").eq("chat_id", chat_id).execute()
            # for message in existing_messages.data:
            #     await websocket.send_json(message)
            # Receive messages from the websocket
            while True:
                # Try to receive a message
                try:
                    text = await websocket.receive_text()
                    print(f"received {text} from {current_user.username}")
                # Close the websocket if the connection is closed
                except WebSocketDisconnect:
                    await websocket.close()
                    connection_handler.close(chat_id, current_user.id)
                    break
                # Append the message to the chat messages
                response = supabase.table("messages").insert({
                    "chat_id": chat_id,
                    "sender_id": current_user.id,
                    "text": text
                }).execute()
                # Broadcast the message to the socket users
                await connection_handler.broadcast(chat_id, response.data[0])
        else:
            # Close the websocket if the current user is not authorized
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    else:
        # Close the websocket if the chat id is invalid
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)


# Define the endpoint for creating a stop
@app.post("/stop")
def create_stop(driver_id: int, address: str, coordinates: str, current_user: User = Depends(get_current_user)):
    # Check if the current user is a passenger
    if current_user.entity == UserEntity.passenger:
        # Insert the stop data into the stop table
        response = supabase.table("stops").insert([{
            "driver_id": driver_id,
            "user_id": current_user.id,
            "address": address,
            "coordinates": coordinates
        }]).execute()
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
            detail="Only passengers can create stops",
        )


# Define the endpoint for listing stops
@app.get("/stops")
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


# Define the endpoint for updating settings
@app.put("/settings")
def update_settings(settings: Settings, current_user: User = Depends(get_current_user)):
    # Check if the settings user id matches the current user id
    if settings.user_id == current_user.id:
        # Query the settings table with the user id
        response = supabase.table("settings").select("*").eq("user_id", settings.user_id).execute()
        # Check if the response has data
        if response.data:
            # Update the settings table with the new settings
            supabase.table("settings").update(settings.model_dump()).eq("id", response.data[0]["id"]).execute()
            # Return the updated settings
            return settings
        else:
            # Insert the settings data into the settings table
            supabase.table("settings").insert([settings.model_dump()]).execute()
            # Return the inserted settings
            return settings
    else:
        # Raise an exception if the settings user id does not match the current user id
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Settings user id does not match current user id",
        )


# Define the endpoint for getting settings
@app.get("/settings")
def get_settings(current_user: User = Depends(get_current_user)) -> Settings:
    # Query the settings table with the current user id
    response = supabase.table("settings").select("*").eq("user_id", current_user.id).execute()
    # Check if the response has data
    if response.data:
        # Return the settings as a Settings object
        return Settings(**response.data[0])
    else:
        # Return an empty Settings object with the current user id
        return Settings(id=0, user_id=current_user.id)


# Define the endpoint for getting statistics
@app.get("/statistics")
def get_statistics(current_user: User = Depends(get_current_user)):
    return {"statistics": "TBD"}


@app.get("/points")
def get_points_sorted(current_user: User = Depends(get_current_user), lat: float = 0, long: float = 0):
    response = supabase.rpc('nearby_points', {"lat": lat, "long": long}).execute()
    return {"points": response.data}



#TODO: debug this endpoint
# @app.put("/points/{point_id}")
# def get_point(current_user: User = Depends(get_current_user), loc_id: int = 0, name: str = "", lat: float = 0, long: float = 0):
#     response = supabase.rpc('update_points', {"point_id": loc_id, "p_name": name, "lat": lat, "long": long}).execute()
#     return {"point": response.data}

@app.post("/points")
def create_point(current_user: User = Depends(get_current_user), loc_id: int = 0, name: str = "", lat: float = 0, long: float = 0):
    response = supabase.rpc('create_points', {"id": loc_id, "name": name, "lat": lat, "long": long}).execute()
    return {"point": response.data}

@app.get("/points_in_range")
def get_points_in_range(current_user: User = Depends(get_current_user), min_lat: float = 0, min_long: float = 0, max_lat: float = 0, max_long: float = 0):
    response = supabase.rpc('points_in_range', {"min_lat": min_lat, "min_long": min_long, "max_lat": max_lat, "max_long": max_long}).execute()
    return {"points": response.data}



if __name__ == "__main__":
    logging.basicConfig(filename='app.log', level=logging.INFO)
    uvicorn.run(app, host="0.0.0.0", port=8000)
