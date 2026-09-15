'use client'

import React, { useState, useMemo } from 'react'
import {
  DollarSign,
  TrendingUp,
  Percent,
  Users,
  Award,
  Sparkles,
  ShieldAlert,
  CheckCircle2,
  RefreshCw,
  Calculator,
  Sliders,
  BarChart3,
  X,
  ArrowUpRight,
  ArrowDownRight,
  Info,
  Download,
  BookmarkPlus,
  HelpCircle,
} from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import {
  NetTuitionYieldModelConfig,
  NetTuitionYieldSummary,
} from './types'
import {
  DEFAULT_NTY_CONFIG,
  computeNetTuitionYield,
  formatPKR,
  GRADE_OPTIONS,
} from './mockData'
import toast from 'react-hot-toast'

export interface NetTuitionYieldModalProps {
  isOpen: boolean
  onClose: () => void
  onApplyTarget?: (summary: NetTuitionYieldSummary, config: NetTuitionYieldModelConfig) => void
  initialConfig?: Partial<NetTuitionYieldModelConfig>
}

interface ScenarioPreset {
  name: string
  description: string
  badge: string
  config: Partial<NetTuitionYieldModelConfig>
}

const SCENARIO_PRESETS: ScenarioPreset[] = [
  {
    name: 'Balanced Merit (Default)',
    description: 'Optimal 85% yield realization with competitive 20% merit discount pool.',
    badge: 'Recommended',
    config: {
      meritDiscountPercent: 20,
      meritQuotaPercent: 25,
      needBasedDiscountPercent: 30,
      needQuotaPercent: 15,
      siblingDiscountPercent: 10,
      siblingQuotaPercent: 20,
      attritionBufferPercent: 5,
    },
  },
  {
    name: 'Aggressive Volume Expansion',
    description: 'High scholarship quotas (40% need + 35% merit) to fill multi-section capacity.',
    badge: 'High Intake',
    config: {
      meritDiscountPercent: 30,
      meritQuotaPercent: 35,
      needBasedDiscountPercent: 40,
      needQuotaPercent: 30,
      siblingDiscountPercent: 15,
      siblingQuotaPercent: 25,
      attritionBufferPercent: 8,
    },
  },
  {
    name: 'Elite Selective (High Yield)',
    description: 'Strict 10% merit cap protecting maximum per-student net yield realization.',
    badge: 'Max Margin',
    config: {
      meritDiscountPercent: 15,
      meritQuotaPercent: 10,
      needBasedDiscountPercent: 20,
      needQuotaPercent: 5,
      siblingDiscountPercent: 5,
      siblingQuotaPercent: 15,
      attritionBufferPercent: 3,
    },
  },
  {
    name: 'STEM & Foundation Endowment',
    description: 'Heavy institutional grants for underprivileged high-aptitude STEM candidates.',
    badge: 'Mission Driven',
    config: {
      meritDiscountPercent: 50,
      meritQuotaPercent: 30,
      needBasedDiscountPercent: 60,
      needQuotaPercent: 25,
      siblingDiscountPercent: 15,
      siblingQuotaPercent: 20,
      attritionBufferPercent: 6,
    },
  },
]

export const NetTuitionYieldModal: React.FC<NetTuitionYieldModalProps> = ({
  isOpen,
  onClose,
  onApplyTarget,
  initialConfig,
}) => {
  const [config, setConfig] = useState<NetTuitionYieldModelConfig>({
    ...DEFAULT_NTY_CONFIG,
    ...initialConfig,
  })

  const [activePreset, setActivePreset] = useState<string>('Balanced Merit (Default)')

  const summary = useMemo(() => computeNetTuitionYield(config), [config])

  const handleApplyPreset = (preset: ScenarioPreset) => {
    setActivePreset(preset.name)
    setConfig((prev) => ({
      ...prev,
      ...preset.config,
    }))
    toast.success(`Applied scenario: ${preset.name}`)
  }

  const handleSaveModel = () => {
    if (onApplyTarget) {
      onApplyTarget(summary, config)
    }
    toast.success(`Net Tuition Yield target of ${formatPKR(summary.totalNetTuitionYieldPKR)} locked for ${config.cohortGrade}!`)
    onClose()
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto p-0 border border-slate-200 dark:border-slate-800 rounded-2xl bg-white dark:bg-slate-900 shadow-2xl">
        {/* Header Ribbon */}
        <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white p-6 pb-7 border-b border-indigo-800/30">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-indigo-500/20 border border-indigo-400/30 rounded-xl text-indigo-300 shadow-inner">
                <Calculator className="w-6 h-6" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-bold tracking-tight text-white">
                    Net Tuition Yield (NTY) Modeler
                  </h2>
                  <span className="px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider bg-indigo-500/30 text-indigo-200 border border-indigo-400/30 rounded-full">
                    RevOps Engine
                  </span>
                </div>
                <p className="text-xs text-slate-300 mt-1">
                  Gross Tuition &minus; Institutional Scholarship Discounts = Net Tuition Yield per Cohort
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-white/10 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Key Formula Bar */}
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3 bg-white/5 backdrop-blur-md border border-white/10 rounded-xl p-3.5 text-xs">
            <div className="flex flex-col">
              <span className="text-slate-400 text-[11px]">Gross Revenue Pool</span>
              <span className="text-base font-bold text-slate-100">
                {formatPKR(summary.projectedEnrolledRevenuePKR)}
              </span>
            </div>
            <div className="flex flex-col border-s-0 sm:border-s border-white/10 sm:ps-3">
              <span className="text-amber-400 text-[11px]">&minus; Scholarship Discounts</span>
              <span className="text-base font-bold text-amber-300">
                {formatPKR(summary.totalInstitutionalDiscountsPKR)}
              </span>
            </div>
            <div className="flex flex-col border-s-0 sm:border-s border-white/10 sm:ps-3">
              <span className="text-emerald-400 text-[11px]">= Net Tuition Yield (NTY)</span>
              <span className="text-base font-bold text-emerald-300">
                {formatPKR(summary.totalNetTuitionYieldPKR)}
              </span>
            </div>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* Scenario Simulation Chips */}
          <div>
            <div className="flex items-center justify-between mb-2.5">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
                Scenario Modeling Presets
              </label>
              <span className="text-[11px] text-slate-500">1-Click revops optimization</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
              {SCENARIO_PRESETS.map((preset) => {
                const isSelected = activePreset === preset.name
                return (
                  <button
                    key={preset.name}
                    onClick={() => handleApplyPreset(preset)}
                    className={`p-3 text-left rounded-xl border transition-all text-xs flex flex-col justify-between ${
                      isSelected
                        ? 'border-indigo-600 bg-indigo-50/70 dark:bg-indigo-950/40 text-indigo-950 dark:text-indigo-200 ring-2 ring-indigo-500/20 shadow-sm'
                        : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 hover:border-slate-300 dark:hover:border-slate-700 text-slate-700 dark:text-slate-300'
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-bold truncate">{preset.name}</span>
                        <span
                          className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                            isSelected
                              ? 'bg-indigo-600 text-white'
                              : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                          }`}
                        >
                          {preset.badge}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-snug line-clamp-2">
                        {preset.description}
                      </p>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Interactive Parameters Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left Column: Cohort Sizing & Base Tuition */}
            <div className="space-y-4 p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/30">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
                <Users className="w-4 h-4 text-indigo-500" />
                Cohort & Base Rate Controls
              </h3>

              {/* Grade Selector */}
              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 block">
                  Cohort Grade Level
                </label>
                <select
                  value={config.cohortGrade}
                  onChange={(e) => setConfig({ ...config, cohortGrade: e.target.value })}
                  className="w-full px-3 py-2 text-xs font-medium rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  {GRADE_OPTIONS.filter((g) => g !== 'All Grades').map((grade) => (
                    <option key={grade} value={grade}>
                      {grade}
                    </option>
                  ))}
                </select>
              </div>

              {/* Target Cohort Capacity */}
              <div>
                <div className="flex justify-between text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  <span>Target Cohort Capacity</span>
                  <span className="font-bold text-indigo-600 dark:text-indigo-400">{config.targetCohortSize} Students</span>
                </div>
                <input
                  type="range"
                  min="20"
                  max="300"
                  step="5"
                  value={config.targetCohortSize}
                  onChange={(e) =>
                    setConfig({ ...config, targetCohortSize: Number(e.target.value) })
                  }
                  className="w-full accent-indigo-600 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg cursor-pointer"
                />
              </div>

              {/* Enrolled Students */}
              <div>
                <div className="flex justify-between text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  <span>Current / Forecast Enrolment</span>
                  <span className="font-bold text-teal-600 dark:text-teal-400">{config.currentEnrolledCount} Enrolled ({summary.capacityFillRatePercent}%)</span>
                </div>
                <input
                  type="range"
                  min="5"
                  max={config.targetCohortSize}
                  step="1"
                  value={config.currentEnrolledCount}
                  onChange={(e) =>
                    setConfig({ ...config, currentEnrolledCount: Number(e.target.value) })
                  }
                  className="w-full accent-teal-600 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg cursor-pointer"
                />
              </div>

              {/* Base Gross Tuition Rate (PKR) */}
              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 block">
                  Base Gross Annual Tuition (PKR)
                </label>
                <div className="relative">
                  <span className="absolute inset-y-0 start-0 flex items-center ps-3 text-xs text-slate-400 font-bold">
                    PKR
                  </span>
                  <input
                    type="number"
                    step="10000"
                    min="100000"
                    max="3000000"
                    value={config.baseAnnualTuitionPKR}
                    onChange={(e) =>
                      setConfig({ ...config, baseAnnualTuitionPKR: Number(e.target.value) })
                    }
                    className="w-full ps-12 pe-3 py-2 text-xs font-bold rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <p className="text-[11px] text-slate-500 mt-1">
                  Average baseline before merit waivers and family assistance.
                </p>
              </div>

              {/* Attrition Buffer */}
              <div>
                <div className="flex justify-between text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  <span>Attrition & Bad-Debt Buffer</span>
                  <span className="font-bold text-amber-600">{config.attritionBufferPercent}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="15"
                  step="1"
                  value={config.attritionBufferPercent}
                  onChange={(e) =>
                    setConfig({ ...config, attritionBufferPercent: Number(e.target.value) })
                  }
                  className="w-full accent-amber-600 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg cursor-pointer"
                />
              </div>
            </div>

            {/* Right Column: Scholarship & Discount Pools */}
            <div className="space-y-4 p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/30">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
                <Percent className="w-4 h-4 text-amber-500" />
                Scholarship & Discount Allocations
              </h3>

              {/* Merit Scholarship */}
              <div className="p-3 bg-white dark:bg-slate-800/80 rounded-lg border border-slate-200 dark:border-slate-700 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-indigo-700 dark:text-indigo-400">Merit Excellence Grants</span>
                  <span className="text-[11px] bg-indigo-100 dark:bg-indigo-950/60 text-indigo-800 dark:text-indigo-300 px-2 py-0.5 rounded-full font-semibold">
                    {config.meritDiscountPercent}% off for {config.meritQuotaPercent}% of cohort
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <label className="text-[11px] text-slate-500 block mb-0.5">Discount Rate</label>
                    <input
                      type="range"
                      min="5"
                      max="75"
                      step="5"
                      value={config.meritDiscountPercent}
                      onChange={(e) =>
                        setConfig({ ...config, meritDiscountPercent: Number(e.target.value) })
                      }
                      className="w-full accent-indigo-600 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] text-slate-500 block mb-0.5">Recipient Quota</label>
                    <input
                      type="range"
                      min="0"
                      max="50"
                      step="5"
                      value={config.meritQuotaPercent}
                      onChange={(e) =>
                        setConfig({ ...config, meritQuotaPercent: Number(e.target.value) })
                      }
                      className="w-full accent-indigo-600 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg"
                    />
                  </div>
                </div>
              </div>

              {/* Need-Based Assistance */}
              <div className="p-3 bg-white dark:bg-slate-800/80 rounded-lg border border-slate-200 dark:border-slate-700 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-amber-700 dark:text-amber-400">Need-Based Financial Aid</span>
                  <span className="text-[11px] bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 px-2 py-0.5 rounded-full font-semibold">
                    {config.needBasedDiscountPercent}% off for {config.needQuotaPercent}% of cohort
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <label className="text-[11px] text-slate-500 block mb-0.5">Discount Rate</label>
                    <input
                      type="range"
                      min="10"
                      max="80"
                      step="5"
                      value={config.needBasedDiscountPercent}
                      onChange={(e) =>
                        setConfig({ ...config, needBasedDiscountPercent: Number(e.target.value) })
                      }
                      className="w-full accent-amber-600 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] text-slate-500 block mb-0.5">Recipient Quota</label>
                    <input
                      type="range"
                      min="0"
                      max="40"
                      step="5"
                      value={config.needQuotaPercent}
                      onChange={(e) =>
                        setConfig({ ...config, needQuotaPercent: Number(e.target.value) })
                      }
                      className="w-full accent-amber-600 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg"
                    />
                  </div>
                </div>
              </div>

              {/* Sibling / Staff Concessions */}
              <div className="p-3 bg-white dark:bg-slate-800/80 rounded-lg border border-slate-200 dark:border-slate-700 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-teal-700 dark:text-teal-400">Sibling & Staff Concessions</span>
                  <span className="text-[11px] bg-teal-100 dark:bg-teal-950/60 text-teal-800 dark:text-teal-300 px-2 py-0.5 rounded-full font-semibold">
                    {config.siblingDiscountPercent}% off for {config.siblingQuotaPercent}% of cohort
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <label className="text-[11px] text-slate-500 block mb-0.5">Discount Rate</label>
                    <input
                      type="range"
                      min="5"
                      max="30"
                      step="5"
                      value={config.siblingDiscountPercent}
                      onChange={(e) =>
                        setConfig({ ...config, siblingDiscountPercent: Number(e.target.value) })
                      }
                      className="w-full accent-teal-600 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] text-slate-500 block mb-0.5">Recipient Quota</label>
                    <input
                      type="range"
                      min="0"
                      max="50"
                      step="5"
                      value={config.siblingQuotaPercent}
                      onChange={(e) =>
                        setConfig({ ...config, siblingQuotaPercent: Number(e.target.value) })
                      }
                      className="w-full accent-teal-600 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* RevOps Analytics & Yield Realization Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* 1. Net Yield per Student */}
            <div className="p-4 rounded-xl border border-emerald-200 dark:border-emerald-900/50 bg-emerald-50/50 dark:bg-emerald-950/20">
              <div className="flex items-center justify-between text-xs text-emerald-800 dark:text-emerald-300 font-semibold mb-1">
                <span>Net Yield / Student</span>
                <TrendingUp className="w-4 h-4 text-emerald-600" />
              </div>
              <div className="text-lg font-extrabold text-emerald-950 dark:text-emerald-100">
                {formatPKR(summary.netTuitionYieldPerStudentPKR)}
              </div>
              <div className="text-[11px] text-emerald-700 dark:text-emerald-400 mt-1 flex items-center gap-1">
                <span className="font-bold">{(summary.yieldRealizationRatePercent)}%</span> of gross sticker rate
              </div>
            </div>

            {/* 2. Total Institutional Aid */}
            <div className="p-4 rounded-xl border border-amber-200 dark:border-amber-900/50 bg-amber-50/50 dark:bg-amber-950/20">
              <div className="flex items-center justify-between text-xs text-amber-800 dark:text-amber-300 font-semibold mb-1">
                <span>Total Aid & Discounts</span>
                <Award className="w-4 h-4 text-amber-600" />
              </div>
              <div className="text-lg font-extrabold text-amber-950 dark:text-amber-100">
                {formatPKR(summary.totalInstitutionalDiscountsPKR)}
              </div>
              <div className="text-[11px] text-amber-700 dark:text-amber-400 mt-1">
                Institutional investment in cohort
              </div>
            </div>

            {/* 3. Realization Rate */}
            <div className="p-4 rounded-xl border border-indigo-200 dark:border-indigo-900/50 bg-indigo-50/50 dark:bg-indigo-950/20">
              <div className="flex items-center justify-between text-xs text-indigo-800 dark:text-indigo-300 font-semibold mb-1">
                <span>Yield Realization Rate</span>
                <BarChart3 className="w-4 h-4 text-indigo-600" />
              </div>
              <div className="text-lg font-extrabold text-indigo-950 dark:text-indigo-100">
                {summary.yieldRealizationRatePercent}%
              </div>
              <div className="text-[11px] text-indigo-700 dark:text-indigo-400 mt-1">
                Benchmark: 78% &ndash; 88%
              </div>
            </div>

            {/* 4. Breakeven Threshold */}
            <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/40">
              <div className="flex items-center justify-between text-xs text-slate-700 dark:text-slate-300 font-semibold mb-1">
                <span>Breakeven Threshold</span>
                <ShieldAlert className="w-4 h-4 text-slate-500" />
              </div>
              <div className="text-lg font-extrabold text-slate-900 dark:text-slate-100">
                {summary.breakevenThresholdStudents} <span className="text-xs font-normal text-slate-500">Students</span>
              </div>
              <div className="text-[11px] text-slate-500 mt-1">
                {config.currentEnrolledCount >= summary.breakevenThresholdStudents ? (
                  <span className="text-emerald-600 font-semibold flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Breakeven achieved
                  </span>
                ) : (
                  <span className="text-rose-500 font-semibold">
                    {summary.breakevenThresholdStudents - config.currentEnrolledCount} more students to breakeven
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 bg-slate-50 dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between rounded-b-2xl">
          <button
            onClick={() => {
              setConfig(DEFAULT_NTY_CONFIG)
              setActivePreset('Balanced Merit (Default)')
              toast('Reset to default yield parameters')
            }}
            className="px-3.5 py-2 text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white flex items-center gap-1.5 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Reset Defaults
          </button>
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg hover:bg-slate-50 transition-all shadow-sm"
            >
              Cancel
            </button>
            <button
              onClick={handleSaveModel}
              className="px-5 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-all shadow-md flex items-center gap-2"
            >
              <BookmarkPlus className="w-4 h-4" />
              Lock Cohort Target ({formatPKR(summary.totalNetTuitionYieldPKR)})
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
