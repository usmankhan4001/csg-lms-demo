'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import {
  Boxes,
  DollarSign,
  BookOpen,
  Truck,
  Building2,
  CheckCircle2,
  Clock,
  Search,
  Download,
  AlertTriangle,
  TrendingUp,
  CreditCard,
  Send,
  MapPin,
  Users,
  Navigation,
  Sparkles,
  Wifi,
  ShieldCheck,
  RotateCw,
  Bell
} from 'lucide-react'
import { useOrgMembership, useOrg } from '@components/Contexts/OrgContext'
import { PersonaSwitcher } from '@/components/ems/PersonaSwitcher'

interface BookLoan {
  id: string
  title: string
  borrower: string
  rollNo: string
  borrowDate: string
  dueDate: string
  status: 'ACTIVE' | 'OVERDUE' | 'RETURNED'
  isbn: string
}

interface BusRoute {
  id: string
  routeNumber: string
  routeName: string
  driver: string
  passengersBoarded: number
  capacity: number
  currentStatus: 'ON_TIME' | 'TRAFFIC_DELAY' | 'COMPLETED'
  nextStop: string
  eta: string
}

export default function OperationsPortalPage() {
  const { orgslug } = useOrgMembership()
  const org = useOrg() as any

  const [activeTab, setActiveTab] = useState<'fees' | 'library' | 'transport' | 'facilities'>('fees')
  const [reminderSent, setReminderSent] = useState<string | null>(null)

  // Library Loans State
  const [loans, setLoans] = useState<BookLoan[]>([
    {
      id: 'L-101',
      title: 'Quantum Mechanics & Wave Packets',
      borrower: 'Maya Chen',
      rollNo: 'MC-104',
      borrowDate: 'Sep 10, 2026',
      dueDate: 'Oct 05, 2026',
      status: 'ACTIVE',
      isbn: '978-0131103627',
    },
    {
      id: 'L-102',
      title: 'Advanced Inorganic Chemistry (Vol 2)',
      borrower: 'Julian Drake',
      rollNo: 'JD-105',
      borrowDate: 'Aug 28, 2026',
      dueDate: 'Sep 11, 2026',
      status: 'OVERDUE',
      isbn: '978-0471199571',
    },
    {
      id: 'L-103',
      title: 'Clean Code: Handbook of Agile Software',
      borrower: 'Liam Vance',
      rollNo: 'LV-101',
      borrowDate: 'Sep 02, 2026',
      dueDate: 'Sep 23, 2026',
      status: 'ACTIVE',
      isbn: '978-0132350884',
    },
  ])

  // Bus Routes Fleet State
  const [busRoutes, setBusRoutes] = useState<BusRoute[]>([
    {
      id: 'BUS-01',
      routeNumber: 'Route 1',
      routeName: 'North Ridge & Downtown',
      driver: 'Arthur Pendelton',
      passengersBoarded: 34,
      capacity: 38,
      currentStatus: 'ON_TIME',
      nextStop: 'Oakwood Crossing',
      eta: '4 mins',
    },
    {
      id: 'BUS-02',
      routeNumber: 'Route 2',
      routeName: 'Metro East Expressway',
      driver: 'Elena Gomez',
      passengersBoarded: 29,
      capacity: 32,
      currentStatus: 'TRAFFIC_DELAY',
      nextStop: 'Highland Park Blvd',
      eta: '12 mins (+8m delay)',
    },
    {
      id: 'BUS-03',
      routeNumber: 'Route 3',
      routeName: 'West Hills & Valley Hub',
      driver: 'Kareem Said',
      passengersBoarded: 36,
      capacity: 36,
      currentStatus: 'COMPLETED',
      nextStop: 'Campus Drop-off Zone',
      eta: 'Completed',
    },
  ])

  const handleSendReminder = (loanId: string) => {
    setReminderSent(loanId)
    setTimeout(() => setReminderSent(null), 3000)
  }

  return (
    <div className="flex flex-col min-h-screen">
      {/* Persona Header Switcher */}
      <PersonaSwitcher
        currentPortal="operations"
        breadcrumbs={[{ label: 'School Operations Desk' }]}
        actions={
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-purple-50 px-3 py-1 text-xs font-bold text-purple-800 border border-purple-200">
              Operations & Logistics
            </span>
          </div>
        }
      />

      <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-8">
        {/* Title & Navigation Tabs */}
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-black tracking-tight text-gray-900 sm:text-3xl">
                School Operations Desk
              </h1>
              <span className="rounded-full bg-purple-100 px-2.5 py-0.5 text-xs font-extrabold text-purple-800 border border-purple-200">
                Logistics Hub
              </span>
            </div>
            <p className="mt-1 text-sm text-gray-500">
              Fee collection cashflow, library catalog circulation, GPS transport telemetry & campus facilities.
            </p>
          </div>

          <div className="flex items-center rounded-xl bg-gray-100 p-1 border border-gray-200">
            <button
              onClick={() => setActiveTab('fees')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                activeTab === 'fees'
                  ? 'bg-white text-gray-900 shadow-xs'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <DollarSign className="size-3.5" />
              <span>Fee Billing</span>
            </button>
            <button
              onClick={() => setActiveTab('library')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                activeTab === 'library'
                  ? 'bg-white text-gray-900 shadow-xs'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <BookOpen className="size-3.5" />
              <span>Library & Holds</span>
            </button>
            <button
              onClick={() => setActiveTab('transport')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                activeTab === 'transport'
                  ? 'bg-white text-gray-900 shadow-xs'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Truck className="size-3.5" />
              <span>Transport Telemetry</span>
            </button>
          </div>
        </div>

        {/* Tab 1: Fee Collection & Cashflow */}
        {activeTab === 'fees' && (
          <div className="space-y-8">
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
              <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-xs">
                <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Today's Collections</span>
                <div className="mt-2 flex items-baseline justify-between">
                  <span className="text-2xl font-black text-gray-900">$48,250.00</span>
                  <span className="text-xs font-bold text-emerald-600">+12% vs avg</span>
                </div>
                <p className="mt-1 text-xs text-gray-400">38 payments processed via Stripe & Wire</p>
              </div>

              <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-xs">
                <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Term 2 Collection Rate</span>
                <div className="mt-2 flex items-baseline justify-between">
                  <span className="text-2xl font-black text-gray-900">97.4%</span>
                  <span className="text-xs font-bold text-emerald-600">On Target</span>
                </div>
                <p className="mt-1 text-xs text-gray-400">$3.8M total invoiced this term</p>
              </div>

              <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-xs">
                <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Outstanding Arrears</span>
                <div className="mt-2 flex items-baseline justify-between">
                  <span className="text-2xl font-black text-rose-600">$142,500.00</span>
                  <span className="text-xs font-bold text-gray-500">22 Families</span>
                </div>
                <p className="mt-1 text-xs text-gray-400">Automated SMS payment reminders active</p>
              </div>
            </div>

            <div className="rounded-3xl border border-gray-200 bg-white p-6 sm:p-8 shadow-xs space-y-4">
              <div className="flex items-center justify-between border-b border-gray-100 pb-4">
                <div>
                  <h3 className="text-base font-bold text-gray-900">Recent Payment Transactions</h3>
                  <p className="text-xs text-gray-400">Live feed of reconciled student fee receipts</p>
                </div>
                <button
                  onClick={() => alert('Exporting reconciliation CSV...')}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 transition"
                >
                  <Download className="size-3.5" />
                  <span>Export CSV</span>
                </button>
              </div>

              <div className="overflow-hidden rounded-2xl border border-gray-200">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-gray-200 bg-gray-50/70 text-gray-500 font-semibold">
                    <tr>
                      <th className="px-4 py-3">Receipt #</th>
                      <th className="px-4 py-3">Payer / Student</th>
                      <th className="px-4 py-3">Fee Item</th>
                      <th className="px-4 py-3">Amount</th>
                      <th className="px-4 py-3">Method</th>
                      <th className="px-4 py-3 text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 bg-white">
                    {[
                      { id: 'RCP-9941', payer: 'Sarah Chen (Maya Chen)', item: 'Term 2 STEM Lab Fee', amount: '$420.00', method: 'Stripe 1-Click', status: 'SETTLED' },
                      { id: 'RCP-9940', payer: 'Robert Vance (Liam Vance)', item: 'Annual Tuition Installment 2', amount: '$4,800.00', method: 'Direct Debit ACH', status: 'SETTLED' },
                      { id: 'RCP-9939', payer: 'Dr. Tariq Al-Mansoor (Noah)', item: 'Robotics Competition Registration', amount: '$200.00', method: 'Credit Card', status: 'SETTLED' },
                    ].map((row) => (
                      <tr key={row.id} className="hover:bg-gray-50/60 transition">
                        <td className="px-4 py-3 font-mono font-bold text-gray-400">{row.id}</td>
                        <td className="px-4 py-3 font-bold text-gray-900">{row.payer}</td>
                        <td className="px-4 py-3 text-gray-600">{row.item}</td>
                        <td className="px-4 py-3 font-mono font-bold text-gray-900">{row.amount}</td>
                        <td className="px-4 py-3 text-gray-500">{row.method}</td>
                        <td className="px-4 py-3 text-right">
                          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-extrabold text-emerald-800">
                            {row.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Library & Catalog Holds */}
        {activeTab === 'library' && (
          <div className="space-y-6">
            <div className="rounded-3xl border border-gray-200 bg-white p-6 sm:p-8 shadow-xs space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-100 pb-4">
                <div>
                  <h3 className="text-base font-bold text-gray-900">Campus Library Catalog & Circulation Desk</h3>
                  <p className="text-xs text-gray-400">Track active book loans, overdue items & reservations</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-purple-100 px-2.5 py-1 text-xs font-bold text-purple-800">
                    4,820 Titles in Catalog
                  </span>
                </div>
              </div>

              {reminderSent && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs font-bold text-emerald-800 flex items-center gap-2 animate-in fade-in">
                  <CheckCircle2 className="size-4 text-emerald-600" />
                  <span>Automated return reminder SMS sent to student and guardian.</span>
                </div>
              )}

              <div className="overflow-hidden rounded-2xl border border-gray-200">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-gray-200 bg-gray-50/70 text-gray-500 font-semibold">
                    <tr>
                      <th className="px-4 py-3">Loan ID</th>
                      <th className="px-4 py-3">Book Title / ISBN</th>
                      <th className="px-4 py-3">Borrower</th>
                      <th className="px-4 py-3">Due Date</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 bg-white">
                    {loans.map((loan) => (
                      <tr key={loan.id} className="hover:bg-gray-50/60 transition">
                        <td className="px-4 py-3 font-mono font-bold text-gray-400">{loan.id}</td>
                        <td className="px-4 py-3">
                          <div className="flex flex-col">
                            <span className="font-bold text-gray-900">{loan.title}</span>
                            <span className="font-mono text-[10px] text-gray-400">{loan.isbn}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span className="font-semibold text-gray-800">{loan.borrower}</span>
                          <span className="block text-[10px] text-gray-400">#{loan.rollNo}</span>
                        </td>
                        <td className="px-4 py-3 font-medium text-gray-700">{loan.dueDate}</td>
                        <td className="px-4 py-3">
                          <span
                            className={`rounded-full px-2 py-0.5 text-[10px] font-extrabold ${
                              loan.status === 'OVERDUE'
                                ? 'bg-rose-100 text-rose-800 border border-rose-200'
                                : 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                            }`}
                          >
                            {loan.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          {loan.status === 'OVERDUE' ? (
                            <button
                              type="button"
                              onClick={() => handleSendReminder(loan.id)}
                              className="inline-flex items-center gap-1 rounded-lg bg-rose-600 px-2.5 py-1 text-xs font-bold text-white hover:bg-rose-700 shadow-2xs transition"
                            >
                              <Send className="size-3" />
                              <span>Send Notice</span>
                            </button>
                          ) : (
                            <button
                              type="button"
                              onClick={() => alert(`Marked ${loan.title} as returned.`)}
                              className="rounded-lg border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 transition"
                            >
                              Return
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Transport & Fleet Telemetry */}
        {activeTab === 'transport' && (
          <div className="space-y-6">
            <div className="rounded-3xl border border-gray-200 bg-white p-6 sm:p-8 shadow-xs space-y-6">
              <div className="flex items-center justify-between border-b border-gray-100 pb-4">
                <div>
                  <h3 className="text-base font-bold text-gray-900">Transport Fleet Telemetry & GPS Tracking</h3>
                  <p className="text-xs text-gray-400">Live GPS tracking and RFID student tap-on counts</p>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-emerald-600 font-bold">
                  <Wifi className="size-4 animate-pulse" />
                  <span>GPS Telemetry Online</span>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {busRoutes.map((bus) => (
                  <div
                    key={bus.id}
                    className="rounded-2xl border border-gray-200 bg-gray-50/50 p-5 space-y-3 transition hover:bg-white hover:shadow-xs"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Truck className="size-4 text-purple-600" />
                        <span className="font-bold text-xs text-gray-900">{bus.routeNumber}</span>
                      </div>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-extrabold ${
                          bus.currentStatus === 'ON_TIME'
                            ? 'bg-emerald-100 text-emerald-800'
                            : bus.currentStatus === 'TRAFFIC_DELAY'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-blue-100 text-blue-800'
                        }`}
                      >
                        {bus.currentStatus.replace('_', ' ')}
                      </span>
                    </div>

                    <h4 className="text-xs font-bold text-gray-900">{bus.routeName}</h4>
                    <p className="text-[11px] text-gray-500">Driver: {bus.driver}</p>

                    <div className="rounded-xl bg-white p-3 border border-gray-100 space-y-1.5 text-xs">
                      <div className="flex justify-between">
                        <span className="text-gray-400">Next Stop</span>
                        <span className="font-bold text-gray-800">{bus.nextStop}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-400">ETA</span>
                        <span className="font-bold text-indigo-600">{bus.eta}</span>
                      </div>
                      <div className="flex justify-between border-t border-gray-100 pt-1.5">
                        <span className="text-gray-400">Students Boarded</span>
                        <span className="font-bold text-gray-900">
                          {bus.passengersBoarded} / {bus.capacity}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
