import datetime
from typing import List, Optional
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


# ── Live class as a school module (M02): scheduling, recording, coursework ──


class ScheduleLiveClassRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    start_time: datetime.datetime
    end_time: Optional[datetime.datetime] = None
    section_id: Optional[int] = Field(None, description="Class section this belongs to")
    course_id: Optional[int] = Field(None, description="Course this belongs to")
    description: Optional[str] = None
    teacher_id: Optional[int] = Field(
        None,
        description=(
            "Host teacher. Ignored for a teacher scheduling their own class -- "
            "they are the host. Only an admin may schedule on someone's behalf."
        ),
    )
    recording_enabled: bool = Field(
        False,
        description=(
            "Opt in to recording this class. Off by default: these are rooms "
            "full of children, so recording is never implicit."
        ),
    )


class LiveClassRecordingRead(BaseModel):
    """Recording state, always honest about why there is no recording."""

    enabled: bool
    shared_with_students: bool
    status: str
    note: Optional[str] = None
    url: Optional[str] = None
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    duration_seconds: Optional[float] = None


class LiveClassCourseworkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    activity_id: int
    attached_by_user_id: int
    note: Optional[str] = None
    created_at: datetime.datetime


class LiveClassDetailRead(BaseModel):
    """A scheduled class as the management UI consumes it."""

    id: int
    title: str
    description: Optional[str] = None
    room_name: str
    teacher_id: int
    section_id: Optional[int] = None
    course_id: Optional[int] = None
    start_time: datetime.datetime
    end_time: Optional[datetime.datetime] = None
    status: str = Field(..., description="SCHEDULED | LIVE | ENDED | CANCELLED")
    cancelled_reason: Optional[str] = None
    recording: LiveClassRecordingRead
    coursework: List[LiveClassCourseworkRead] = []
    can_host: bool = Field(
        False, description="Whether the CALLER may host/manage this class"
    )


class AttachCourseworkRequest(BaseModel):
    activity_id: int = Field(..., description="An existing Learnhouse activity id")
    note: Optional[str] = None


class CancelLiveClassRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)


class SetRecordingRequest(BaseModel):
    enabled: bool


class ShareRecordingRequest(BaseModel):
    shared: bool
