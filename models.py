import os
from enum import Enum
from pydantic import BaseModel
from supabase import create_client, Client
from typing import Optional


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
