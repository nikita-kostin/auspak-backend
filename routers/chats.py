from datetime import datetime
from fastapi import status, APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from typing import Any, Dict

from dependencies import get_current_user
from models import supabase, Chat, User, UserEntity
from routers.connection_handler import connection_handler


router = APIRouter(prefix="/chats", tags=["chats"])


# Define the endpoint for creating a chat
@router.post("/")
def create_chat(user_id: int, current_user: User = Depends(get_current_user)):
    # Check if the current user is a driver
    if current_user.entity == UserEntity.driver:
        # Query the user table with the 2nd user id
        response = supabase.table("users").select("entity").eq("id", user_id).execute()
        # Check if response has data
        if response.data:
            # Check if the 2nd user is a driver
            if response.data[0]["entity"] == UserEntity.driver.value:
                # Raise an exception if the 2nd user is a driver
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Drivers cannot create chats with other drivers",
                )
        else:
            # Raise an exception if user not found
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No user with given id found"
            )
        # Check if the chat between the users already exists
        # Query the chat table with driver and user id
        response = supabase.table("chats").select("*").eq("driver_id", current_user.id).eq("user_id", user_id).execute()
        # Check if response has data
        if response.data:
            # Return the existing chat id
            return {"chat_id": response.data[0]["id"]}
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


def supabase_chat_to_response(current_user: User, chat: Dict[str, Any]) -> Dict[str, Any]:
    last_message = "" if chat["last_message"] is None else chat["last_message"]
    last_message_sender_id = "" if chat["last_message_sender_id"] is None else chat["last_message_sender_id"]
    if last_message_sender_id == current_user.id:
        last_message = "You: " + last_message

    last_message_time = "" if chat["ts"] is None else datetime.fromisoformat(chat["ts"]).strftime("%H:%M")

    return {
        "id": chat["id"],
        "name": chat["name"],
        "last_message": last_message,
        "user_type": chat["user_type"],
        "time": last_message_time
    }


# Define the endpoint for listing chats
@router.get("/")
def list_chats(current_user: User = Depends(get_current_user)):
    response = supabase.rpc("get_chats", {"caller_id": current_user.id}).execute()

    if not response:
        return []

    return [supabase_chat_to_response(current_user, chat) for chat in response.data]


@router.get("/history/{chat_id}")
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


def filter_user(user: dict, query: str):
    first_last_match = f"{user['first_name']} {user['last_name']}".startswith(query)
    last_first_match = f"{user['last_name']} {user['first_name']}".startswith(query)
    stop_name_match = user["stop_name"].startswith(query)
    return first_last_match or last_first_match or stop_name_match


# List users
@router.get("/users")
def list_users(current_user: User = Depends(get_current_user), query: str = "", entity: UserEntity = None):
    users = supabase.rpc('chat_users', {}).execute().data
    if query != "":
        users = [user for user in users if filter_user(user, query)]
    unique_user_ids = set()
    users = [user for user in users if user["user_id"] not in unique_user_ids and (unique_user_ids.add(user["user_id"]) or True)]
    if entity is not None:
        users = [user for user in users if user["entity"] == entity.value]
    return {"users": users}


# Define the websocket endpoint for opening a chat
@router.websocket("/{chat_id}")
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
            print(f"user {current_user.id} entered the chat")
            connection_handler.register(chat_id, current_user.id, websocket)
            existing_messages = supabase.table("messages").select("*").eq("chat_id", chat_id).execute()
            for message in existing_messages.data:
                await websocket.send_json(message)
            # Receive messages from the websocket
            while True:
                # Try to receive a message
                try:
                    text = await websocket.receive_text()
                    print(f"received {text} from {current_user.id}")
                # Close the websocket if the connection is closed
                except WebSocketDisconnect:
                    if websocket.client_state != WebSocketState.DISCONNECTED:
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
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    else:
        # Close the websocket if the chat id is invalid
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
