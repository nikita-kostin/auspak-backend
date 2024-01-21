from datetime import datetime
from fastapi import status, APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from typing import Any, Dict

from dependencies import get_current_user
from models import supabase, Chat, Message, User, UserEntity
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


def get_chat_info(current_user: User, chat_as_model: Chat) -> Dict[str, Any]:
    recipient_id = chat_as_model.user_id if current_user.entity == UserEntity.driver else chat_as_model.driver_id
    recipient_as_supabase_response = supabase.table("users").select("*").eq("id", recipient_id).execute()
    # If the user cannot be found, we should fail to indicate data inconsistency
    if not recipient_as_supabase_response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not fetch user with id=${recipient_id} from database"
        )

    recipient_as_model = User(**recipient_as_supabase_response.data[0])
    message_as_supabase_response = supabase \
        .table("messages") \
        .select("*") \
        .eq("chat_id", chat_as_model.id) \
        .order("created_at") \
        .execute()

    chat_to_return = {
        "id": chat_as_model.id,
        "name": recipient_as_model.first_name + " " + recipient_as_model.last_name,
        "last_message": "",
        "user_type": recipient_as_model.entity,
        "time": ""
    }

    # No message found in chat
    if not message_as_supabase_response.data:
        return chat_to_return

    message_as_model = Message(**message_as_supabase_response.data[-1])

    # Construct text to show
    if message_as_model.sender_id == current_user.id:
        chat_to_return["last_message"] += "You: "
    chat_to_return["last_message"] += message_as_model.text

    # Construct message time in the following format: "HH:MM"
    dt = datetime.fromisoformat(message_as_model.created_at)
    chat_to_return["time"] = f"{dt.hour}:{dt.minute}"

    return chat_to_return


# Define the endpoint for listing chats
@router.get("/")
def list_chats(current_user: User = Depends(get_current_user)):
    # Query the chat table with the current user id
    user_id_field = "driver_id" if current_user.entity == UserEntity.driver else "user_id"
    query = supabase.table("chats").select("*").eq(user_id_field, current_user.id)
    chats_as_supabase_response = query.execute()

    if not chats_as_supabase_response.data:
        return []

    chats_as_models = [Chat(**chat) for chat in chats_as_supabase_response.data]
    return [get_chat_info(current_user, chat_as_model) for chat_as_model in chats_as_models]


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
            print(f"user {current_user.username} entered the chat")
            connection_handler.register(chat_id, current_user.id, websocket)
            existing_messages = supabase.table("messages").select("*").eq("chat_id", chat_id).execute()
            for message in existing_messages.data:
                await websocket.send_json(message)
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
