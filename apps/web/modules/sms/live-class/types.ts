/** Mirrors `apps/api/src/schemas/sms_live_class.py`. */

export interface LiveClassSessionRead {
  id: number
  section_id: number | null
  course_id: number | null
  teacher_id: number
  title: string
  room_name: string
  start_time: string
  end_time: string | null
  is_active: boolean
  recording_url: string | null
  created_at: string
}

export interface LiveClassSessionWithTokenResponse {
  session: LiveClassSessionRead
  token: string
  livekit_url: string
}

export interface LiveClassTokenResponse {
  room_name: string
  token: string
  livekit_url: string
  participant_id: string
  participant_name: string
  is_teacher: boolean
}

export interface CreateLiveClassSessionRequest {
  title: string
  teacher_id: number
  section_id?: number
  course_id?: number
  room_name?: string
  start_time?: string
  end_time?: string
}

/**
 * One row of `GET /boards/org/{org_id}` (`apps/api/src/routers/boards/boards.py:71`),
 * narrowed to what the in-class whiteboard picker needs.
 *
 * A board is the unit the collab server knows about: it is the only document
 * name `apps/collab` will open (see `LiveClassWhiteboard.tsx`), so the
 * whiteboard surface is a board, not a room-scoped document.
 */
export interface LiveClassBoardOption {
  id: number
  board_uuid: string
  name: string
}

export interface LiveClassAttendanceLogRead {
  id: number
  session_id: number
  student_id: number
  joined_at: string
  left_at: string | null
  duration_minutes: number | null
  created_at: string
}

// ---------------------------------------------------------------------------
// Scheduled classes (the management window). Mirrors the `/live/classes/*`
// half of `apps/api/src/routers/live_classes.py`, which is a different surface
// from the ad-hoc `rooms/*` calls above: a scheduled class has a lifecycle,
// a recording policy and attached coursework, where a room is just a room.
// ---------------------------------------------------------------------------

/** `apps/api/src/db/sms_live_class.py` LiveClassStatus. */
export type LiveClassStatus = 'SCHEDULED' | 'LIVE' | 'ENDED' | 'CANCELLED'

/**
 * `apps/api/src/db/sms_live_class.py` RecordingStatus.
 *
 * UNAVAILABLE and FAILED are deliberately separate states and must stay that
 * way in the UI: UNAVAILABLE means this deployment has no object storage, so
 * recording was never possible; FAILED means it was attempted and did not
 * work. Collapsing them tells a teacher their recording broke when in fact
 * nobody ever configured storage, and sends them chasing the wrong problem.
 */
export type RecordingStatus =
  | 'NOT_REQUESTED'
  | 'UNAVAILABLE'
  | 'PENDING'
  | 'RECORDING'
  | 'PROCESSING'
  | 'READY'
  | 'FAILED'

export interface LiveClassRecordingRead {
  enabled: boolean
  shared_with_students: boolean
  status: RecordingStatus
  /** The server's own explanation. Render it verbatim; never invent one. */
  note: string | null
  /** Null unless a real file exists. Never synthesise a URL. */
  url: string | null
  started_at: string | null
  completed_at: string | null
  duration_seconds: number | null
}

export interface LiveClassCourseworkRead {
  id: number
  session_id: number
  activity_id: number
  attached_by_user_id: number
  note: string | null
  created_at: string
}

export interface LiveClassDetailRead {
  id: number
  title: string
  description: string | null
  room_name: string
  teacher_id: number
  section_id: number | null
  course_id: number | null
  start_time: string
  end_time: string | null
  status: LiveClassStatus
  cancelled_reason: string | null
  recording: LiveClassRecordingRead
  coursework: LiveClassCourseworkRead[]
  /**
   * Computed server-side FOR THE CALLER. Gate host controls on this rather
   * than re-deriving permissions from roles in the browser -- the server
   * already knows whether this particular person may host this particular
   * class, and a second client-side rule would eventually disagree with it.
   */
  can_host: boolean
}

export interface ScheduleLiveClassRequest {
  title: string
  start_time: string
  end_time?: string | null
  section_id?: number | null
  course_id?: number | null
  description?: string | null
  /** Only an admin may schedule on another teacher's behalf. */
  teacher_id?: number | null
  /**
   * Opt IN to recording. Off by default on the server and deliberately off
   * here: these are rooms full of children, so recording is never implicit.
   */
  recording_enabled?: boolean
}

export interface AttachCourseworkRequest {
  activity_id: number
  note?: string | null
}
