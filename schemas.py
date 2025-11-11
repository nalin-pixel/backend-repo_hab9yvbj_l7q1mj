"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal

# Example schemas (you can keep using these elsewhere if needed):

class User(BaseModel):
    """
    Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product" (lowercase of class name)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# Agent-specific schemas for this project

ActionType = Literal[
    "tap",
    "long_press",
    "type_text",
    "swipe",
    "open_app",
    "back",
    "home",
    "recent_apps",
    "search",
    "call_contact",
    "send_message",
    "toggle_wifi",
    "toggle_bluetooth",
    "open_url",
    "unknown"
]

class DeviceAction(BaseModel):
    """A single low-level action the device companion app can execute"""
    type: ActionType
    target: Optional[str] = Field(None, description="Target element/app/package/text")
    args: Optional[dict] = Field(default_factory=dict, description="Additional arguments like coordinates, duration, etc.")
    status: Literal["pending", "sent", "executed", "failed"] = "pending"
    error: Optional[str] = None

class Command(BaseModel):
    """High-level user command which is planned into actions"""
    text: str = Field(..., description="User provided instruction in natural language")
    language: Optional[str] = Field(None, description="Detected language code, e.g., bn, en")
    intent: Optional[str] = Field(None, description="Best-effort intent label")
    actions: List[DeviceAction] = Field(default_factory=list, description="Planned low-level actions")
    status: Literal["planned", "in_progress", "completed", "failed"] = "planned"
    device_id: Optional[str] = Field(None, description="Remote device identifier if paired")
