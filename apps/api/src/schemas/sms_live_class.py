import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class CreateLiveClassSessionRequest(BaseModel):
    title: str = Field(..., description="Classroom session title / topic")
    teacher_id: int = Field(..., description="Teacher user ID hosting the live class")
    section_id: Optional[int] = Field(None, description="Optional associated school section ID")
    course_id: Optional[int] = Field(None, description="Optional associated course ID")
    room_name: Optional[str] = Field(None, description="Unique room name (auto-generated if omitted)")
    start_time: Optional[datetime.datetime] = Field(None, description="Scheduled start time")
    end_time: Optional[datetime.datetime] = Field(None, description="Scheduled end time")


class LiveClassSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    section_id: Optional[int] = None
    course_id: Optional[int] = None
    teacher_id: int
    title: str
    room_name: str
    start_time: datetime.datetime
    end_time: Optional[datetime.datetime] = None
    is_active: bool
    recording_url: Optional[str] = None
    created_at: datetime.datetime


class LiveClassTokenRequest(BaseModel):
    participant_id: str = Field(..., description="Unique participant identity/user ID")
    participant_name: str = Field(..., description="Display name of the participant")
    is_teacher: bool = Field(False, description="Whether participant has teacher / publisher privileges")
    can_publish: Optional[bool] = Field(None, description="Explicit publish permission (audio/video/screen)")
    can_subscribe: bool = Field(True, description="Whether participant can subscribe to audio/video tracks")


class LiveClassTokenResponse(BaseModel):
    room_name: str
    token: str
    livekit_url: str
    participant_id: str
    participant_name: str
    is_teacher: bool


class LiveClassAttendanceRequest(BaseModel):
    student_id: int = Field(..., description="Student user ID")
    action: str = Field("join", description="'join' or 'leave'")
    timestamp: Optional[datetime.datetime] = Field(None, description="Timestamp of the event (defaults to now)")


class LiveClassAttendanceLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    student_id: int
    joined_at: datetime.datetime
    left_at: Optional[datetime.datetime] = None
    duration_minutes: Optional[float] = None
    created_at: datetime.datetime


class LiveClassSessionWithTokenResponse(BaseModel):
    session: LiveClassSessionRead
    token: str
    livekit_url: str
