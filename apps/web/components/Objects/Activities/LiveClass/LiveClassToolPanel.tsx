'use client'

/**
 * The side panel that turns a video call into a class: chat, plus the
 * school's existing Learnhouse tools running alongside the stream.
 *
 * DESIGN NOTE — why Boards and Playgrounds are iframed rather than imported.
 *
 * `BoardCanvas` is hard-coded `h-screen` (BoardCanvas.tsx:757) and
 * `PlaygroundEditor` sets `minHeight: calc(100vh - 120px)`. Both therefore
 * size themselves to the viewport, not to their container, so mounting them
 * directly inside a panel produces a board taller than the space it is in.
 * Making them embeddable needs an additive prop on each — a change to
 * components this module does not own, so it was deliberately not made.
 *
 * Iframing the real routes (`/board/{uuid}`, `/playground/{uuid}`) composes
 * the ACTUAL shipped feature instead: same code, same Yjs collaboration, same
 * permissions, no divergent copy to maintain. It also sidesteps the height
 * problem entirely, because an iframe gives the page its own viewport. The
 * cost is a heavier mount and no direct prop-passing, which is the right
 * trade against forking a second Boards implementation.
 *
 * HOW STUDENTS FOLLOW THE TEACHER: the teacher's selection is broadcast over
 * LiveKit's data channel (topic `lh-class-tool`) — the same transport chat
 * already uses. No new backend contract, and no polling. Only a host may
 * broadcast; a student receiving one follows along. The board itself is
 * already collaborative, so everyone lands in the same live document.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useDataChannel } from '@livekit/components-react'
import {
  ChalkboardSimple,
  ChatCircleDots,
  Cube,
  FolderOpen,
} from '@phosphor-icons/react'
import { useQuery } from '@tanstack/react-query'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { useOrg } from '@components/Contexts/OrgContext'
import { getBoards } from '@services/boards/boards'
import { getOrgPlaygrounds } from '@services/playgrounds/playgrounds'
import { LH_INPUT, LH_SECONDARY_BUTTON } from '@/components/widgets'
import LiveClassChat from './LiveClassChat'

export type ToolTab = 'chat' | 'board' | 'playground' | 'coursework'

/** Broadcast when a host opens a tool, so students follow along. */
const TOOL_TOPIC = 'lh-class-tool'

interface SharedTool {
  tab: ToolTab
  /** board_uuid or playground_uuid; absent for chat. */
  uuid?: string
  name?: string
}

const TABS: { id: ToolTab; label: string; Icon: any }[] = [
  { id: 'chat', label: 'Chat', Icon: ChatCircleDots },
  { id: 'board', label: 'Board', Icon: ChalkboardSimple },
  { id: 'playground', label: 'Playground', Icon: Cube },
  { id: 'coursework', label: 'Coursework', Icon: FolderOpen },
]

/** A picked resource rendered through its own real route. */
function EmbeddedTool({ src, title }: { src: string; title: string }) {
  return (
    <iframe
      src={src}
      title={title}
      className="h-full w-full border-0"
      // The board needs clipboard + fullscreen to be genuinely usable.
      allow="clipboard-read; clipboard-write; fullscreen"
    />
  )
}

/** Picker over the org's real boards / playgrounds. */
function ResourcePicker({
  items,
  isLoading,
  error,
  emptyLabel,
  idKey,
  nameKey,
  onPick,
  inputId,
}: {
  items: any[]
  isLoading: boolean
  error: unknown
  emptyLabel: string
  idKey: string
  nameKey: string
  onPick: (uuid: string, name: string) => void
  inputId: string
}) {
  const [filter, setFilter] = useState('')

  const shown = useMemo(() => {
    const q = filter.trim().toLowerCase()
    if (!q) return items
    return items.filter((it) =>
      String(it?.[nameKey] ?? '').toLowerCase().includes(q)
    )
  }, [items, filter, nameKey])

  if (isLoading) {
    return <p className="p-3 text-sm text-gray-400">Loading…</p>
  }
  if (error) {
    return (
      <p className="p-3 text-sm text-rose-600">
        Could not load these. Try reopening the panel.
      </p>
    )
  }
  if (items.length === 0) {
    return <p className="p-3 text-sm text-gray-500">{emptyLabel}</p>
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-gray-100 p-2">
        <input
          id={inputId}
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Search…"
          autoComplete="off"
          className={LH_INPUT}
        />
      </div>
      <ul className="flex-1 min-h-0 overflow-y-auto p-2">
        {shown.map((it) => {
          const uuid = String(it?.[idKey] ?? '')
          const name = String(it?.[nameKey] ?? 'Untitled')
          if (!uuid) return null
          return (
            <li key={uuid}>
              <button
                type="button"
                id={`live-class-pick-${uuid}`}
                onClick={() => onPick(uuid, name)}
                className="w-full truncate rounded-lg px-3 py-2 text-left text-sm text-gray-700 transition-colors hover:bg-gray-100"
              >
                {name}
              </button>
            </li>
          )
        })}
        {shown.length === 0 && (
          <li className="px-3 py-2 text-sm text-gray-400">Nothing matches.</li>
        )}
      </ul>
    </div>
  )
}

export function LiveClassToolPanel({ isHost }: { isHost: boolean }) {
  const session = useLHSession() as any
  const orgCtx = useOrg() as any
  const access_token = session?.data?.tokens?.access_token
  // useOrg() returns { org, isUserPartOfTheOrg, orgslug } -- the org is nested,
  // so reading `.id` straight off the context silently yields undefined and
  // every picker query stays disabled.
  const orgId = orgCtx?.org?.id

  const [tab, setTab] = useState<ToolTab>('chat')
  const [shared, setShared] = useState<SharedTool | null>(null)

  // Students follow whatever a host opens. Hosts ignore their own echo.
  const onToolMessage = useCallback(
    (msg: any) => {
      if (isHost) return
      try {
        const parsed: SharedTool = JSON.parse(
          new TextDecoder().decode(msg.payload)
        )
        if (!parsed?.tab) return
        setShared(parsed.uuid ? parsed : null)
        setTab(parsed.tab)
      } catch {
        // A malformed broadcast must not take the panel down.
      }
    },
    [isHost]
  )

  const { send } = useDataChannel(TOOL_TOPIC, onToolMessage)

  const broadcast = useCallback(
    (payload: SharedTool) => {
      if (!isHost || !send) return
      try {
        send(new TextEncoder().encode(JSON.stringify(payload)), {
          reliable: true,
        })
      } catch {
        // Sharing is a convenience; failing to broadcast must not stop the
        // teacher from using the tool themselves.
      }
    },
    [isHost, send]
  )

  const boards = useQuery({
    queryKey: ['live-class', 'boards', orgId],
    queryFn: () => getBoards(orgId as number, access_token),
    enabled: tab === 'board' && !!orgId && !!access_token && !shared,
    staleTime: 60_000,
  })

  const playgrounds = useQuery({
    queryKey: ['live-class', 'playgrounds', orgId],
    queryFn: () => getOrgPlaygrounds(orgId as number, access_token),
    enabled: tab === 'playground' && !!orgId && !!access_token && !shared,
    staleTime: 60_000,
  })

  // Switching tabs clears a resource from a different tab.
  useEffect(() => {
    if (shared && shared.tab !== tab) setShared(null)
  }, [tab, shared])

  const pick = (nextTab: ToolTab) => (uuid: string, name: string) => {
    const next = { tab: nextTab, uuid, name }
    setShared(next)
    broadcast(next)
  }

  const closeResource = () => {
    setShared(null)
    broadcast({ tab })
  }

  const renderBody = () => {
    if (tab === 'chat') return <LiveClassChat />

    if (tab === 'coursework') {
      // Deliberately not built: attaching coursework to a class needs an
      // endpoint that is being written right now. Guessing its shape would
      // mean shipping UI against an imagined contract.
      return (
        <p className="p-3 text-sm text-gray-500">
          Attaching coursework to a live class isn’t available yet — the
          endpoint for it is still being built.
        </p>
      )
    }

    if (shared?.uuid) {
      const src =
        shared.tab === 'board'
          ? `/board/${shared.uuid}`
          : `/playground/${shared.uuid}`
      return (
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between gap-2 border-b border-gray-100 px-3 py-1.5">
            <span className="truncate text-xs font-medium text-gray-600">
              {shared.name}
            </span>
            {isHost && (
              <button
                type="button"
                id="live-class-close-resource"
                onClick={closeResource}
                className="shrink-0 text-xs text-gray-400 transition-colors hover:text-gray-700"
              >
                Close
              </button>
            )}
          </div>
          <div className="min-h-0 flex-1">
            <EmbeddedTool src={src} title={shared.name || shared.tab} />
          </div>
        </div>
      )
    }

    // Students cannot pick — they follow the teacher, so an idle panel says so
    // rather than offering a control that would desync the class.
    if (!isHost) {
      return (
        <p className="p-3 text-sm text-gray-500">
          Your teacher hasn’t opened a {tab} yet. It will appear here when they
          do.
        </p>
      )
    }

    if (tab === 'board') {
      return (
        <ResourcePicker
          items={Array.isArray(boards.data) ? boards.data : []}
          isLoading={boards.isLoading}
          error={boards.error}
          emptyLabel="No boards in this organisation yet."
          idKey="board_uuid"
          nameKey="name"
          onPick={pick('board')}
          inputId="live-class-board-search"
        />
      )
    }

    return (
      <ResourcePicker
        items={Array.isArray(playgrounds.data) ? playgrounds.data : []}
        isLoading={playgrounds.isLoading}
        error={playgrounds.error}
        emptyLabel="No playgrounds in this organisation yet."
        idKey="playground_uuid"
        nameKey="name"
        onPick={pick('playground')}
        inputId="live-class-playground-search"
      />
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col rounded-xl bg-white nice-shadow">
      <div
        role="tablist"
        aria-label="Class tools"
        className="flex shrink-0 items-center gap-1 border-b border-gray-100 p-1.5"
      >
        {TABS.map(({ id, label, Icon }) => {
          const active = tab === id
          return (
            <button
              key={id}
              id={`live-class-tab-${id}`}
              role="tab"
              type="button"
              aria-selected={active}
              onClick={() => setTab(id)}
              className={[
                'inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium transition-colors',
                active
                  ? 'bg-gray-900 text-white'
                  : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800',
              ].join(' ')}
            >
              <Icon size={14} weight={active ? 'fill' : 'regular'} />
              <span className="hidden sm:inline">{label}</span>
            </button>
          )
        })}
      </div>

      <div className="min-h-0 flex-1">{renderBody()}</div>

      {isHost && tab !== 'chat' && tab !== 'coursework' && !shared && (
        <p className="shrink-0 border-t border-gray-100 px-3 py-1.5 text-[11px] text-gray-400">
          Opening one shares it with everyone in the class.
        </p>
      )}
    </div>
  )
}

export default LiveClassToolPanel
