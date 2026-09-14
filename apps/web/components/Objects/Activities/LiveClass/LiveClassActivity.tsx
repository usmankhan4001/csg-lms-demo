'use client'

/**
 * A live class rendered INSIDE the course player.
 *
 * The existing `/live/{roomId}` page uses the same `@livekit/components-react`
 * `VideoConference`, but is full-screen (h-screen) and takes `is_teacher`
 * from the client. This variant is embedded in the activity container and
 * gets its grant from `activities/liveclass/{uuid}/join`, which decides
 * host vs participant server-side from the caller's course permissions.
 *
 * Joining is explicit rather than on-mount: landing on an activity should
 * not silently switch on someone's camera and announce them to the room.
 *
 * A class is more than a video call, so the room is laid out as stream plus
 * tools — chat, and the school's existing Boards and Playgrounds running
 * beside it (see LiveClassToolPanel for why those are composed rather than
 * reimplemented). The panel collapses on narrow screens, where a phone has no
 * room for both and the video is what matters.
 */

import '@livekit/components-styles'
import { useState } from 'react'
import { LiveKitRoom, VideoConference } from '@livekit/components-react'
import {
  CaretDoubleLeft,
  CaretDoubleRight,
  VideoCamera,
  WarningCircle,
} from '@phosphor-icons/react'
import { Loader2 } from 'lucide-react'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { joinLiveClassActivity } from '@services/courses/activities'
import LiveClassToolPanel from './LiveClassToolPanel'

type JoinState =
  | { status: 'idle' }
  | { status: 'joining' }
  | { status: 'joined'; token: string; livekitUrl: string; isHost: boolean }
  | { status: 'error'; message: string }

function LiveClassActivity({ activity }: { activity: any }) {
  const session = useLHSession() as any
  const access_token = session?.data?.tokens?.access_token
  const [state, setState] = useState<JoinState>({ status: 'idle' })
  const [panelOpen, setPanelOpen] = useState(true)

  const activityUuid: string = activity?.activity_uuid ?? ''
  const description: string = activity?.details?.description ?? ''

  const join = async () => {
    setState({ status: 'joining' })
    try {
      const res = await joinLiveClassActivity(activityUuid, access_token)
      setState({
        status: 'joined',
        token: res.token,
        livekitUrl: res.livekit_url,
        isHost: !!res.is_host,
      })
    } catch (err: any) {
      setState({
        status: 'error',
        message: err?.message || 'Could not join this live class.',
      })
    }
  }

  if (state.status === 'joined') {
    return (
      <div className="relative" style={{ height: '70vh' }}>
        <div className="h-full min-h-0 overflow-hidden rounded-xl">
          <LiveKitRoom
            token={state.token}
            serverUrl={state.livekitUrl}
            connect
            video={state.isHost}
            audio={state.isHost}
            onDisconnected={() => setState({ status: 'idle' })}
            data-lk-theme="default"
            style={{ height: '100%' }}
          >
            <div className="flex h-full flex-col gap-3 lg:flex-row">
              <div className="min-h-0 min-w-0 flex-1 overflow-hidden rounded-xl">
                <VideoConference />
              </div>

              {/* The panel lives INSIDE LiveKitRoom: useChat and
                  useDataChannel both need the room context. */}
              <div
                className={[
                  'min-h-0 shrink-0 transition-all duration-200',
                  panelOpen
                    ? 'h-64 lg:h-auto lg:w-80'
                    : 'h-0 overflow-hidden lg:h-auto lg:w-0',
                ].join(' ')}
              >
                {panelOpen && <LiveClassToolPanel isHost={state.isHost} />}
              </div>
            </div>
          </LiveKitRoom>
        </div>

        <button
          type="button"
          id="live-class-toggle-panel"
          onClick={() => setPanelOpen((o) => !o)}
          aria-expanded={panelOpen}
          className="absolute right-4 top-4 z-10 hidden items-center gap-1 rounded-lg bg-white/90 px-2 py-1 text-xs text-gray-600 nice-shadow transition-colors hover:text-gray-900 lg:inline-flex"
        >
          {panelOpen ? (
            <>
              <CaretDoubleRight size={13} /> Hide tools
            </>
          ) : (
            <>
              <CaretDoubleLeft size={13} /> Show tools
            </>
          )}
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center justify-center gap-4 py-12 text-center">
      <div className="flex items-center justify-center size-14 rounded-full bg-pink-50">
        <VideoCamera size={26} weight="duotone" className="text-pink-400" />
      </div>

      <div className="space-y-1">
        <h3 className="text-lg font-bold text-gray-900">{activity?.name}</h3>
        {description && (
          <p className="max-w-md text-sm text-gray-500">{description}</p>
        )}
      </div>

      {state.status === 'error' && (
        <p className="flex items-center gap-1.5 text-sm text-rose-600">
          <WarningCircle size={16} weight="fill" />
          {state.message}
        </p>
      )}

      <button
        type="button"
        id="live-class-join"
        onClick={join}
        disabled={state.status === 'joining' || !activityUuid}
        className="inline-flex items-center justify-center gap-2 h-10 px-6 text-sm font-medium text-white bg-black rounded-lg hover:bg-gray-800 transition-colors disabled:opacity-50"
      >
        {state.status === 'joining' ? (
          <>
            <Loader2 size={16} className="animate-spin" />
            Joining…
          </>
        ) : (
          'Join live class'
        )}
      </button>

      <p className="text-xs text-gray-400">
        Your camera and microphone stay off until you join.
      </p>
    </div>
  )
}

export default LiveClassActivity
