from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

class University(BaseModel):
    uni_id: str = Field(max_length=5)
    university_name: str = Field(max_length=25)
    city: str = Field(max_length=25)
    state: str = Field(max_length=25)

class Fest(BaseModel):
    fest_id: str = Field(max_length=5)
    fest_name: str = Field(max_length=25)
    year: date
    head_teamID: Optional[str] = Field(None, max_length=5)
    uni_id: str = Field(max_length=5)

class Team(BaseModel):
    team_id: str = Field(max_length=5)
    team_name: str = Field(max_length=25)
    team_type: int = Field(ge=0)  # Added validation for non-negative integers
    fest_id: str = Field(max_length=5)
    uni_id: str = Field(max_length=5)

class Member(BaseModel):
    mem_id: str = Field(max_length=5)
    mem_name: str = Field(max_length=25)
    DOB: date = Field(description="Date of Birth")
    super_memID: Optional[str] = Field(None, max_length=5)
    team_id: str = Field(max_length=5)
    uni_id: str = Field(max_length=5)

class Event(BaseModel):
    event_id: str = Field(max_length=5)
    event_name: str = Field(max_length=25)
    building: str = Field(max_length=15)
    floor: str = Field(max_length=10)
    room_no: int = Field(gt=0)  # Added validation for positive integers
    price: Decimal = Field(ge=0, le=1500.00)  # Added validation based on CHECK constraint
    team_id: str = Field(max_length=5)
    uni_id: str = Field(max_length=5)

class EventConduction(BaseModel):
    event_id: str = Field(max_length=5)
    date_of_conduction: date
    uni_id: str = Field(max_length=5)

class Participant(BaseModel):
    SRN: str = Field(max_length=10)
    name: str = Field(max_length=25)
    department: str = Field(max_length=20)
    semester: int = Field(ge=1, le=8)  # Added validation for valid semester range
    gender: int = Field(ge=0, le=2)  # Added validation for gender codes (0, 1, 2)
    uni_id: str = Field(max_length=5)

class Visitor(BaseModel):
    SRN: str = Field(max_length=10)
    name: str = Field(max_length=25)
    age: int = Field(ge=0)  # Added validation for non-negative age
    gender: int = Field(ge=0, le=2)  # Added validation for gender codes
    uni_id: str = Field(max_length=5)

class Registration(BaseModel):
    event_id: str = Field(max_length=5)
    SRN: str = Field(max_length=10)
    registration_id: str = Field(max_length=5)
    uni_id: str = Field(max_length=5)