'use client'

/**
 * The in-class collaborative whiteboard.
 *
 * WHY THIS IS A REAL BOARD AND NOT A NEW Yjs DOCUMENT.
 *
 * The collab server (`apps/collab/src/index.ts`) is board-shaped in three
 * independent places, and a per-session document would fail all three:
 *
 *   1. Naming. `extractBoardUuid()` matches `^board:(.+)$` and `onAuthenticate`
 *      throws `Invalid document name` for anything else -- so a document called
 *      `liveclass:{room_name}` is refused before a single update is exchanged.
 *   2. Authorization. It verifies the caller's Learnhouse JWT and then asks
 *      `GET /api/v1/boards/{uuid}/membership`. There is no live-class
 *      equivalent, so a room-scoped document has nothing to authorize against.
 *   3. Persistence. `Database.fetch`/`store` read and write
 *      `/api/v1/boards/{uuid}/ydoc` (plus a `collab:ydoc:{uuid}` Redis cache).
 *      A document with no board row has nowhere to be saved.
 *
 * So the whiteboard IS a board: the host opens one of the org's boards and
 * everyone lands in the same `board:{uuid}` document -- the same Hocuspocus
 * server, the same Yjs CRDT, the same auth and the same persistence the rest of
 * the product already uses. Nothing here speaks Yjs or opens a websocket; it
 * composes the shipped board surface instead of forking a second one.
 *
 * WHY IT IS IFRAMED RATHER THAN IMPORTED.
 *
 * `BoardCanvas` is hard-coded `h-screen` (BoardCanvas.tsx:757) and sizes itself
 * to the viewport, not to its container, so mounting it inside a dialog
 * produces a board taller than the dialog. An iframe gives it its own viewport,
 * which is exactly the trade `LiveClassToolPanel.tsx` already makes for the
 * same reason.
 *
 * HOW EVERYONE GETS TO THE SAME BOARD: the host's choice is broadcast over
 * LiveKit's data channel (topic `lh-class-whiteboard`) -- the same transport
 * chat uses, so no new backend contract and no polling. Only a host broadcasts;
 * everyone else follows.
 */

import { useCallback, useState } from 'react'
import { useDataChannel } from '@livekit/components-react'
import { Loader2, PenTool } from 'lucide-react'
import { useApiResource } from '@/lib/api/useApiResource'
import { EmptyState, LH_INPUT, LH_SECONDARY_BUTTON, SchoolDialog } from '@/components/widgets'
import { listOrgBoards } from '../api'

/** Broadcast when a host opens a board, so the rest of the class follows. */
const WHITEBOARD_TOPIC = 'lh-class-whiteboard'

interface SharedBoard {
  board_uuid: string
  name: string
}

interface LiveClassWhiteboardProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Server-granted host status, not a client guess (see LiveClassRoom). */
  isHost: boolean
  /** The caller's org, from `GET /sms/me`. Absent => the picker cannot load. */
  orgId?: number
}

export function LiveClassWhiteboard({ open, onOpenChange, isHost, orgId }: LiveClassWhiteboardProps) {
  const [picked, setPicked] = useState<SharedBoard | null>(null)
  const [frameReady, setFrameReady] = useState(false)

  // Students follow whatever a host opens. Hosts ignore their own echo.
  const onBoardMessage = useCallback(
    (msg: any) => {
      if (isHost) return
      try {
        const parsed: SharedBoard = JSON.parse(new TextDecoder().decode(msg.payload))
        if (!parsed || typeof parsed.board_uuid !== 'string') return
        // An empty uuid is the host CLOSING the board -- clearing here is what
        // stops the class staring at a whiteboard the teacher has moved on from.
        setPicked(parsed.board_uuid ? parsed : null)
        setFrameReady(false)
      } catch {
        // A malformed broadcast must not take the whiteboard down.
      }
    },
    [isHost]
  )

  const { send } = useDataChannel(WHITEBOARD_TOPIC, onBoardMessage)

  const boards = useApiResource(() => listOrgBoards(orgId as number), [orgId], {
    // Only the host picks, and only while the dialog is actually open -- a
    // closed dialog must not be polling the org's boards behind the class.
    skip: !open || !isHost || orgId === undefined || !!picked,
    isEmpty: (rows) => rows.length === 0,
  })

  const pick = (board: SharedBoard) => {
    setPicked(board)
    setFrameReady(false)
    if (!isHost || !send) return
    try {
      send(new TextEncoder().encode(JSON.stringify(board)), { reliable: true })
    } catch {
      // Sharing is a convenience; failing to broadcast must not stop the host
      // from using the board themselves.
    }
  }

  const closeBoard = () => {
    setPicked(null)
    setFrameReady(false)
    if (!isHost || !send) return
    try {
      send(new TextEncoder().encode(JSON.stringify({ board_uuid: '', name: '' })), { reliable: true })
    } catch {
      // As above: never let a failed broadcast block the host.
    }
  }

  const renderBody = () => {
    if (picked?.board_uuid) {
      return (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <p className="truncate text-xs font-medium text-gray-600">{picked.name}</p>
            {isHost && (
              <button
                type="button"
                id="live-class-whiteboard-close-board"
                onClick={closeBoard}
                className={LH_SECONDARY_BUTTON}
              >
                Close board
              </button>
            )}
          </div>
          <div className="relative h-[65vh] w-full overflow-hidden rounded-xl border border-gray-200 bg-white">
            {!frameReady && (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-white">
                <Loader2 className="size-5 animate-spin text-gray-400" />
              </div>
            )}
            <iframe
              key={picked.board_uuid}
              src={`/board/${picked.board_uuid}`}
              title={picked.name || 'Whiteboard'}
              className="h-full w-full border-0"
              onLoad={() => setFrameReady(true)}
              // The board needs clipboard + fullscreen to be genuinely usable.
              allow="clipboard-read; clipboard-write; fullscreen"
            />
          </div>
        </div>
      )
    }

    // A student cannot pick: they follow the teacher, so an idle whiteboard
    // says so rather than offering a control that would desync the class.
    if (!isHost) {
      return (
        <p className="py-8 text-center text-sm text-gray-500">
          Your teacher hasn’t opened a whiteboard yet. It will appear here when
          they do.
        </p>
      )
    }

    if (orgId === undefined) {
      return (
        <EmptyState
          icon={PenTool}
          tone="caution"
          title="No school linked to this account"
          description="The whiteboard is opened from your school’s boards, and this account isn’t linked to a school yet."
        />
      )
    }

    if (boards.status === 'loading') {
      return (
        <div className="flex items-center justify-center gap-2 py-10 text-sm text-gray-400">
          <Loader2 className="size-4 animate-spin" />
          Loading boards…
        </div>
      )
    }

    if (boards.status === 'error') {
      const kind = boards.error?.kind
      // Offline and permission-denied are different problems with different
      // fixes, so they do not share a message (DESIGN-SYSTEM.md §4).
      const offline = kind === 'network'
      const denied = kind === 'permission_denied' || kind === 'unauthenticated'
      return (
        <EmptyState
          icon={PenTool}
          tone={offline ? 'caution' : 'critical'}
          title={offline ? 'You appear to be offline' : denied ? 'Boards aren’t available to you' : 'Could not load boards'}
          description={
            offline
              ? 'The whiteboard needs a connection to the collaboration server. Reconnect and try again.'
              : denied
                ? 'Boards are switched off for your account or your school’s plan. Ask an administrator if you need them.'
                : (boards.error?.message ?? 'Something went wrong loading your boards.')
          }
          action={{ label: 'Try again', onClick: boards.refetch }}
        />
      )
    }

    if (boards.status === 'empty') {
      return (
        <EmptyState
          icon={PenTool}
          title="No boards yet"
          description="The in-class whiteboard opens one of your school’s boards. Create one from Boards and it will show up here."
        />
      )
    }

    return <BoardPicker rows={boards.data ?? []} onPick={pick} />
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Whiteboard"
      description="A shared board everyone in the class can draw on."
      className="max-h-[90vh] overflow-y-auto sm:max-w-5xl"
    >
      {renderBody()}
    </SchoolDialog>
  )
}

function BoardPicker({
  rows,
  onPick,
}: {
  rows: { board_uuid: string; name: string }[]
  onPick: (board: SharedBoard) => void
}) {
  const [filter, setFilter] = useState('')
  const q = filter.trim().toLowerCase()
  const shown = q ? rows.filter((r) => (r.name ?? '').toLowerCase().includes(q)) : rows

  return (
    <div className="flex flex-col gap-2">
      <input
        id="live-class-whiteboard-search"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="Search boards…"
        autoComplete="off"
        className={LH_INPUT}
      />
      <ul className="max-h-64 min-h-0 overflow-y-auto rounded-xl border border-gray-100">
        {shown.map((row) => (
          <li key={row.board_uuid}>
            <button
              type="button"
              id={`live-class-whiteboard-pick-${row.board_uuid}`}
              onClick={() => onPick({ board_uuid: row.board_uuid, name: row.name })}
              className="w-full truncate px-3 py-2 text-start text-sm text-gray-700 transition-colors hover:bg-gray-100"
            >
              {row.name || 'Untitled board'}
            </button>
          </li>
        ))}
        {shown.length === 0 && (
          <li className="px-3 py-2 text-sm text-gray-400">Nothing matches.</li>
        )}
      </ul>
      <p className="text-[11px] text-gray-400">
        Opening one shares it with everyone in the class.
      </p>
    </div>
  )
}

export default LiveClassWhiteboard
