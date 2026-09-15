import React from 'react'
import { SessionGate } from '@components/Contexts/LHSessionContext'

export default async function PortalsLayout(props: {
  children: React.ReactNode
  params: Promise<{ orgslug: string }>
}) {
  return (
    <SessionGate>
      <div className="min-h-screen bg-[#f8f9fb] text-gray-900 selection:bg-indigo-500 selection:text-white antialiased">
        {props.children}
      </div>
    </SessionGate>
  )
}
