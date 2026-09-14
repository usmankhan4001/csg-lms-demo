/**
 * Real fetch calls against `apps/api/src/routers/live_classes.py` (mounted
 * at `/api/v1/live` -- NOT under `/sms`, see `src/router.py`). Real,
 * self-hosted LiveKit WebRTC video: room create/join tokens come from these
 * calls, actual media flows browser<->LiveKit directly (see
 * `LiveClassRoom.tsx`), and attendance is authoritatively recorded
 * server-side from LiveKit's own webhooks
 * (`src/routers/live_class_webhooks.py`) -- the client-driven
 * `/attendance` endpoint below is kept only for the rare fallback case
 * where the webhook delivery itself is unreachable.
 */

import { apiDelete, apiGet, apiPost, apiPut, toQueryString } from '@/lib/api/api-client'
import type {
  AttachCourseworkRequest,
  CreateLiveClassSessionRequest,
  LiveClassAttendanceLogRead,
  LiveClassCourseworkRead,
  LiveClassDetailRead,
  LiveClassRecordingRead,
  LiveClassSessionRead,
  LiveClassSessionWithTokenResponse,
  LiveClassTokenResponse,
  ScheduleLiveClassRequest,
} from './types'

export function createLiveClassSession(payload: CreateLiveClassSessionRequest): Promise<LiveClassSessionWithTokenResponse> {
  return apiPost<LiveClassSessionWithTokenResponse>('/live/rooms/create', payload)
}

export function getParticipantToken(
  roomName: string,
  payload: { participant_id: string; participant_name: string; is_teacher: boolean; can_publish?: boolean; can_subscribe?: boolean }
): Promise<LiveClassTokenResponse> {
  return apiPost<LiveClassTokenResponse>(`/live/rooms/${encodeURIComponent(roomName)}/token`, payload)
}

export function listActiveLiveRooms(params: { sectionId?: number; courseId?: number; teacherId?: number } = {}): Promise<LiveClassSessionRead[]> {
  const qs = toQueryString({ section_id: params.sectionId, course_id: params.courseId, teacher_id: params.teacherId })
  return apiGet<LiveClassSessionRead[]>(`/live/rooms/active${qs}`)
}

export function endLiveClassSession(roomName: string, recordingUrl?: string): Promise<LiveClassSessionRead> {
  const qs = toQueryString({ recording_url: recordingUrl })
  return apiPost<LiveClassSessionRead>(`/live/rooms/${encodeURIComponent(roomName)}/end${qs}`)
}

export function getRoomAttendanceLogs(roomName: string): Promise<LiveClassAttendanceLogRead[]> {
  return apiGet<LiveClassAttendanceLogRead[]>(`/live/rooms/${encodeURIComponent(roomName)}/attendance`)
}

// ---------------------------------------------------------------------------
// Scheduled classes -- the management window's contract.
//
// Every path below was verified against `apps/api/src/routers/live_classes.py`
// and its mount at `src/router.py:621` (prefix `/live`, NOT `/sms/live`).
// ---------------------------------------------------------------------------

/** `POST /live/classes` -- live_classes.py:525 */
export function scheduleLiveClass(payload: ScheduleLiveClassRequest): Promise<LiveClassDetailRead> {
  return apiPost<LiveClassDetailRead>('/live/classes', payload)
}

/**
 * `GET /live/classes` -- live_classes.py:575
 *
 * `upcoming` is a real server-side filter, not a client slice: the endpoint
 * defaults it to true, so asking for past classes is an explicit request.
 */
export function listLiveClasses(
  params: {
    upcoming?: boolean
    sectionId?: number
    courseId?: number
    teacherId?: number
    campusId?: number
  } = {}
): Promise<LiveClassDetailRead[]> {
  const qs = toQueryString({
    upcoming: params.upcoming,
    section_id: params.sectionId,
    course_id: params.courseId,
    teacher_id: params.teacherId,
    campus_id: params.campusId,
  })
  return apiGet<LiveClassDetailRead[]>(`/live/classes${qs}`)
}

/** `GET /live/classes/{id}` -- live_classes.py:608 */
export function getLiveClass(classId: number): Promise<LiveClassDetailRead> {
  return apiGet<LiveClassDetailRead>(`/live/classes/${classId}`)
}

/** `POST /live/classes/{id}/cancel` -- live_classes.py:622 */
export function cancelLiveClass(classId: number, reason?: string): Promise<LiveClassDetailRead> {
  return apiPost<LiveClassDetailRead>(`/live/classes/${classId}/cancel`, { reason: reason || null })
}

/**
 * `POST /live/classes/{id}/start` -- live_classes.py:794
 *
 * Opens the LiveKit room, begins recording only if the teacher opted in, and
 * returns the HOST's join token.
 */
export function startLiveClass(classId: number): Promise<LiveClassSessionWithTokenResponse> {
  return apiPost<LiveClassSessionWithTokenResponse>(`/live/classes/${classId}/start`)
}

/** `PUT /live/classes/{id}/recording` -- live_classes.py:645 */
export function setLiveClassRecording(classId: number, enabled: boolean): Promise<LiveClassDetailRead> {
  return apiPut<LiveClassDetailRead>(`/live/classes/${classId}/recording`, { enabled })
}

/**
 * `PUT /live/classes/{id}/recording/share` -- live_classes.py:667
 *
 * Separate from enabling recording on purpose: recording a class and
 * publishing it to the students in it are two different decisions.
 */
export function shareLiveClassRecording(classId: number, shared: boolean): Promise<LiveClassDetailRead> {
  return apiPut<LiveClassDetailRead>(`/live/classes/${classId}/recording/share`, { shared })
}

/**
 * `GET /live/classes/{id}/recording` -- live_classes.py:688
 *
 * 403 for a student when the recording is unshared or they were not enrolled
 * in that section. Surface that as "not shared with you", never as an error.
 */
export function getLiveClassRecording(classId: number): Promise<LiveClassRecordingRead> {
  return apiGet<LiveClassRecordingRead>(`/live/classes/${classId}/recording`)
}

/** `GET /live/classes/{id}/coursework` -- live_classes.py:760 */
export function listLiveClassCoursework(classId: number): Promise<LiveClassCourseworkRead[]> {
  return apiGet<LiveClassCourseworkRead[]>(`/live/classes/${classId}/coursework`)
}

/** `POST /live/classes/{id}/coursework` -- live_classes.py:732 */
export function attachLiveClassCoursework(
  classId: number,
  payload: AttachCourseworkRequest
): Promise<LiveClassCourseworkRead> {
  return apiPost<LiveClassCourseworkRead>(`/live/classes/${classId}/coursework`, payload)
}

/** `DELETE /live/classes/{id}/coursework/{activityId}` -- live_classes.py:775 */
export function detachLiveClassCoursework(classId: number, activityId: number): Promise<void> {
  return apiDelete<void>(`/live/classes/${classId}/coursework/${activityId}`)
}
