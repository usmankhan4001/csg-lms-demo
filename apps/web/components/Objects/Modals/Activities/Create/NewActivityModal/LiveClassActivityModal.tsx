import React, { useState } from 'react'
import * as Form from '@radix-ui/react-form'
import BarLoader from 'react-spinners/BarLoader'
import { VideoCamera } from '@phosphor-icons/react'

/**
 * Add a live class to a chapter.
 *
 * Unlike the other create modals, this one does not hand a plain object to
 * the generic `submitActivity` path: creating a live class has to provision
 * a LiveKit room server-side, so it goes through its own endpoint via
 * `submitLiveClassActivity` (same shape as `submitExternalVideo`).
 */
function LiveClassActivityModal({ submitLiveClassActivity, chapterId }: any) {
  const [activityName, setActivityName] = useState('')
  const [description, setDescription] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: any) => {
    e.preventDefault()
    setIsSubmitting(true)
    setError(null)
    try {
      await submitLiveClassActivity(
        { name: activityName, description },
        chapterId
      )
    } catch (err: any) {
      // Surface the real reason: the room may fail to provision, and a
      // silent failure would leave the teacher thinking the class exists.
      setError(err?.message || 'Could not create the live class.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Form.Root onSubmit={handleSubmit} className="space-y-4">
      <div
        className="relative flex items-center justify-center h-20 rounded-xl overflow-hidden"
        style={{
          backgroundImage:
            'repeating-linear-gradient(-45deg, transparent, transparent 6px, rgba(251,207,232,0.25) 6px, rgba(251,207,232,0.25) 7px)',
        }}
      >
        <span className="flex items-center gap-2 bg-white nice-shadow rounded-full px-4 py-1.5 text-sm font-medium text-gray-600">
          <VideoCamera size={18} weight="duotone" className="text-pink-400" />
          Live class
        </span>
      </div>

      <div className="rounded-xl nice-shadow p-4 space-y-4">
        <Form.Field name="liveclass-activity-name" className="space-y-1.5">
          <Form.Label className="text-sm font-medium text-gray-700">
            Activity name
          </Form.Label>
          <Form.Message match="valueMissing" className="text-xs text-red-500">
            Please provide a name
          </Form.Message>
          <Form.Control asChild>
            <input
              id="liveclass-activity-name"
              onChange={(e) => setActivityName(e.target.value)}
              type="text"
              required
              placeholder="e.g. Week 3 — Live Q&A"
              className="w-full h-9 px-3 text-sm rounded-lg bg-gray-50 border border-gray-200 outline-none focus:border-gray-300 focus:ring-1 focus:ring-gray-200 transition-colors"
            />
          </Form.Control>
        </Form.Field>

        <Form.Field name="liveclass-activity-desc" className="space-y-1.5">
          <Form.Label className="text-sm font-medium text-gray-700">
            Description
          </Form.Label>
          <Form.Control asChild>
            <textarea
              id="liveclass-activity-desc"
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What will this session cover?"
              rows={3}
              className="w-full px-3 py-2 text-sm rounded-lg bg-gray-50 border border-gray-200 outline-none focus:border-gray-300 focus:ring-1 focus:ring-gray-200 transition-colors resize-none"
            />
          </Form.Control>
        </Form.Field>

        <p className="text-xs text-gray-400">
          A video room is created now and stays attached to this activity.
          Students join from inside the course; you join as host.
        </p>

        {error && <p className="text-sm text-rose-600">{error}</p>}
      </div>

      <div className="flex justify-end">
        <Form.Submit asChild>
          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex items-center justify-center h-9 px-5 text-sm font-medium text-white bg-black rounded-lg hover:bg-gray-800 transition-colors disabled:opacity-50"
          >
            {isSubmitting ? (
              <BarLoader
                cssOverride={{ borderRadius: 60 }}
                width={60}
                color="#ffffff"
              />
            ) : (
              'Create activity'
            )}
          </button>
        </Form.Submit>
      </div>
    </Form.Root>
  )
}

export default LiveClassActivityModal
