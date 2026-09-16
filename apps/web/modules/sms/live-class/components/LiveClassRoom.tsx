'use client'

/**
 * Real WebRTC video classroom, built on `@livekit/components-react`'s
 * pre-built `VideoConference` (tiles, mic/camera/screen-share controls,
 * participant list, and a chat panel over LiveKit's own data channel --
 * all real, not the hand-rolled demo UI this replaces). Server-verified
 * attendance is recorded automatically by LiveKit's own webhooks
 * (`src/routers/live_class_webhooks.py`) as soon as this component's
 * WebRTC connection actually joins the room -- nothing here needs to log
 * attendance itself.
 *
 * HOST STATUS IS THE SERVER'S ANSWER, NOT A CLIENT GUESS.
 *
 * `POST /live/rooms/{room}/token` ignores the `is_teacher` it is sent and
 * derives host rights itself -- the session's own teacher, or a
 * SCHOOL_ADMIN/SUPER_ADMIN (live_classes.py:153 `_caller_is_host`) -- then
 * echoes what it actually granted. Rendering from that echo rather than from a
 * role string read in the browser is the difference between a SCHOOL_ADMIN
 * host seeing host controls and being handed a participant's UI: the old
 * `roles.includes('TEACHER')` test missed every admin who ever ran a class.
 *
 * The whiteboard (see `LiveClassWhiteboard.tsx`) is a real Learnhouse board
 * opened in a modal from the control bar, so it rides the existing
 * Hocuspocus/Yjs collab service rather than a second one.
 */

import '@livekit/components-styles'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { LiveKitRoom, VideoConference } from '@livekit/components-react'
import { Loader2, PenTool, ShieldAlert, WifiOff } from 'lucide-react'
import { ApiError } from '@/lib/api/api-client'
import { EmptyState } from '@/components/widgets'
import { getParticipantToken } from '../api'
import { LiveClassWhiteboard } from './LiveClassWhiteboard'

interface LiveClassRoomProps {
  roomName: string
  participantId: string
  participantName: string
  /**
   * A HINT, not an authority: the server re-derives host status and echoes it
   * back (see the file comment). Sent so the request describes the caller
   * honestly; every UI decision below uses the granted value instead.
   */
  isHost: boolean
  /** Where to send the user once they leave/disconnect. */
  onLeaveHref: string
  /** The caller's org, from `GET /sms/me`. Used to list boards to draw on. */
  orgId?: number
}

type ConnectState =
  | { status: 'connecting' }
  | { status: 'ready'; token: string; livekitUrl: string; isHost: boolean }
  | { status: 'error'; error: ApiError }

export function LiveClassRoom({ roomName, participantId, participantName, isHost, onLeaveHref, orgId }: LiveClassRoomProps) {
  const router = useRouter()
  const [state, setState] = useState<ConnectState>({ status: 'connecting' })
  const [attempt, setAttempt] = useState(0)
  const [whiteboardOpen, setWhiteboardOpen] = useState(false)

  useEffect(() => {
    let cancelled = false
    setState({ status: 'connecting' })

    getParticipantToken(roomName, {
      participant_id: participantId,
      participant_name: participantName,
      is_teacher: isHost,
    })
      .then((res) => {
        if (cancelled) return
        // `res.is_teacher` is what the server GRANTED, not what was asked for
        // (live_classes.py:341) -- the only host flag this UI may trust.
        setState({ status: 'ready', token: res.token, livekitUrl: res.livekit_url, isHost: res.is_teacher })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const apiError =
          err instanceof ApiError
            ? err
            : new ApiError(0, err instanceof Error ? err.message : 'Could not connect to the live class.', 'unknown')
        setState({ status: 'error', error: apiError })
      })

    return () => {
      cancelled = true
    }
  }, [roomName, participantId, participantName, isHost, attempt])

  if (state.status === 'connecting') {
    return (
      <div className="flex h-screen items-center justify-center bg-neutral-950">
        <div className="flex flex-col items-center gap-3 text-neutral-400">
          <Loader2 className="size-6 animate-spin" />
          <p className="text-sm">Joining live class…</p>
        </div>
      </div>
    )
  }

  if (state.status === 'error') {
    return (
      <div className="flex h-screen items-center justify-center bg-neutral-950">
        <EmptyState
          icon={state.error.kind === 'network' ? WifiOff : ShieldAlert}
          tone={state.error.kind === 'network' ? 'caution' : 'critical'}
          title={errorTitle(state.error)}
          description={errorDescription(state.error)}
          action={
            state.error.kind === 'network' || state.error.kind === 'server'
              ? { label: 'Try again', onClick: () => setAttempt((n) => n + 1) }
              : { label: 'Back to dashboard', href: onLeaveHref }
          }
        />
      </div>
    )
  }

  return (
    <div className="relative h-screen">
      <LiveKitRoom
        token={state.token}
        serverUrl={state.livekitUrl}
        connect
        // Publish ONLY if the server's token actually permits it.
        //
        // services/sms/live_class.py:55 issues `can_publish = is_teacher` unless
        // overridden, so a STUDENT's token forbids publishing. Passing bare
        // `video`/`audio` asked LiveKit to publish camera and mic on connect for
        // everyone -- so a student's browser prompted for camera access, turned
        // the camera light on, then had the publish rejected by the server. The
        // toolbar showed mic/camera buttons that looked live and did nothing.
        //
        // A student can still be granted publish rights per-room (the `can_publish`
        // override exists for exactly that); this follows the grant rather than
        // assuming it, so raising a hand to speak keeps working when it is granted.
        video={state.isHost}
        audio={state.isHost}
        data-lk-theme="default"
        style={{ height: '100vh' }}
        onDisconnected={() => router.push(onLeaveHref)}
      >
        <VideoConference />
        {/* Inside LiveKitRoom: `useDataChannel` needs the room context. */}
        <LiveClassWhiteboard
          open={whiteboardOpen}
          onOpenChange={setWhiteboardOpen}
          isHost={state.isHost}
          orgId={orgId}
        />
      </LiveKitRoom>

      {/* Anchored beside LiveKit's own control bar, which is centred and leaves
          the bottom-left corner free. `lk-button` borrows the control bar's own
          button styling so this reads as part of it. */}
      <button
        type="button"
        id="live-class-whiteboard"
        onClick={() => setWhiteboardOpen(true)}
        className="lk-button absolute bottom-4 start-4 z-10"
      >
        <PenTool size={16} />
        <span className="hidden sm:inline">Whiteboard</span>
      </button>
    </div>
  )
}

/**
 * A 404 from the token endpoint is deliberately ambiguous server-side: a class
 * the caller is not entitled to is indistinguishable from one that does not
 * exist (live_classes.py:187 `_not_found`). So the copy covers both without
 * asserting either -- telling a student "you are not enrolled" would confirm a
 * class exists at another campus, which is the thing the 404 exists to hide.
 */
function errorTitle(error: ApiError): string {
  switch (error.kind) {
    case 'network':
      return 'You appear to be offline'
    case 'permission_denied':
      return 'You can’t join this live class'
    case 'unauthenticated':
      return 'Your session has expired'
    case 'not_found':
      return 'This live class isn’t available'
    case 'validation':
      return 'This live class has ended'
    default:
      return 'Couldn’t join this live class'
  }
}

function errorDescription(error: ApiError): string {
  switch (error.kind) {
    case 'network':
      return 'Joining a live class needs a connection. Reconnect and try again.'
    case 'permission_denied':
      return error.message || 'Your school role doesn’t allow you into this room.'
    case 'unauthenticated':
      return 'Sign in again to rejoin the class.'
    case 'not_found':
      return 'It may have ended, or it may not be a class you’re enrolled in.'
    case 'validation':
      return error.message || 'This class has been concluded and can no longer be joined.'
    default:
      return error.message || 'Something went wrong joining the class.'
  }
}
