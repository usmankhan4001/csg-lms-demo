'use client'

import React, { useState, useMemo } from 'react'
import {
  Plus,
  Trash2,
  Copy,
  ChevronUp,
  ChevronDown,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Clock,
  Percent,
  Sliders,
  RotateCcw,
  BookOpen,
  Award,
  Save,
  Download,
  Upload,
  Info,
  Layers,
} from 'lucide-react'
import {
  Rubric,
  RubricCriterion,
  RubricLevel,
  LatePenaltyConfig,
} from './types'
import {
  RUBRIC_PRESETS,
  SCIENCE_LAB_RUBRIC,
  DEFAULT_LATE_PENALTY_CONFIG,
} from './rubric-presets'
import { LH_CARD, LH_PRIMARY_BUTTON, LH_SECONDARY_BUTTON } from '@/components/widgets/lh-styles'

export interface RubricEditorProps {
  initialRubric?: Rubric
  onSaveRubric?: (rubric: Rubric) => void
  onCancel?: () => void
  readOnly?: boolean
}

export const RubricEditor: React.FC<RubricEditorProps> = ({
  initialRubric,
  onSaveRubric,
  onCancel,
  readOnly = false,
}) => {
  const [rubric, setRubric] = useState<Rubric>(() => initialRubric || SCIENCE_LAB_RUBRIC)
  const [selectedPresetId, setSelectedPresetId] = useState<string>(rubric.id)
  const [activeCriterionIndex, setActiveCriterionIndex] = useState<number>(0)
  const [showLateSettings, setShowLateSettings] = useState<boolean>(true)
  const [savedToast, setSavedToast] = useState<boolean>(false)

  // Calculate sum of criteria weights
  const totalWeight = useMemo(() => {
    return rubric.criteria.reduce((acc, c) => acc + (Number(c.weight) || 0), 0)
  }, [rubric.criteria])

  const isWeightValid = totalWeight === 100

  const handleApplyPreset = (presetId: string) => {
    const found = RUBRIC_PRESETS.find((p) => p.id === presetId)
    if (found) {
      // Clone deeply to prevent mutation
      const cloned = JSON.parse(JSON.stringify(found))
      setRubric(cloned)
      setSelectedPresetId(presetId)
      setActiveCriterionIndex(0)
    }
  }

  const handleAddCriterion = () => {
    const newId = `crit-${Date.now()}`
    const defaultMaxPts = 25
    const newCriterion: RubricCriterion = {
      id: newId,
      title: 'New Analytical Criterion',
      description: 'Describe the specific analytical benchmark evaluated by this criterion.',
      weight: 25,
      maxPoints: defaultMaxPts,
      levels: [
        {
          id: 'exemplary',
          name: 'Exemplary',
          points: defaultMaxPts,
          percentage: 100,
          description: 'Demonstrates comprehensive mastery exceeding standard requirements.',
          color: 'emerald',
        },
        {
          id: 'proficient',
          name: 'Proficient',
          points: Math.round(defaultMaxPts * 0.8),
          percentage: 80,
          description: 'Meets benchmark standards with solid execution and minor omissions.',
          color: 'blue',
        },
        {
          id: 'developing',
          name: 'Developing',
          points: Math.round(defaultMaxPts * 0.6),
          percentage: 60,
          description: 'Demonstrates emerging understanding; notable gaps in precision or rigor.',
          color: 'amber',
        },
        {
          id: 'novice',
          name: 'Novice',
          points: Math.round(defaultMaxPts * 0.4),
          percentage: 40,
          description: 'Does not yet meet minimum threshold; critical components missing.',
          color: 'rose',
        },
      ],
    }

    setRubric((prev) => ({
      ...prev,
      criteria: [...prev.criteria, newCriterion],
    }))
    setActiveCriterionIndex(rubric.criteria.length)
  }

  const handleDeleteCriterion = (index: number) => {
    if (rubric.criteria.length <= 1) return
    setRubric((prev) => {
      const nextCriteria = prev.criteria.filter((_, i) => i !== index)
      return { ...prev, criteria: nextCriteria }
    })
    if (activeCriterionIndex >= index && activeCriterionIndex > 0) {
      setActiveCriterionIndex(activeCriterionIndex - 1)
    }
  }

  const handleDuplicateCriterion = (index: number) => {
    const target = rubric.criteria[index]
    if (!target) return
    const cloned: RubricCriterion = {
      ...JSON.parse(JSON.stringify(target)),
      id: `crit-${Date.now()}`,
      title: `${target.title} (Copy)`,
    }
    const nextCriteria = [...rubric.criteria]
    nextCriteria.splice(index + 1, 0, cloned)
    setRubric((prev) => ({ ...prev, criteria: nextCriteria }))
    setActiveCriterionIndex(index + 1)
  }

  const handleMoveCriterion = (index: number, direction: 'up' | 'down') => {
    if (direction === 'up' && index === 0) return
    if (direction === 'down' && index === rubric.criteria.length - 1) return

    const targetIdx = direction === 'up' ? index - 1 : index + 1
    const nextCriteria = [...rubric.criteria]
    const temp = nextCriteria[index]
    nextCriteria[index] = nextCriteria[targetIdx]
    nextCriteria[targetIdx] = temp

    setRubric((prev) => ({ ...prev, criteria: nextCriteria }))
    setActiveCriterionIndex(targetIdx)
  }

  const handleUpdateCriterion = (index: number, updates: Partial<RubricCriterion>) => {
    setRubric((prev) => {
      const next = [...prev.criteria]
      next[index] = { ...next[index], ...updates }
      return { ...prev, criteria: next }
    })
  }

  const handleUpdateLevel = (critIndex: number, levelIndex: number, updates: Partial<RubricLevel>) => {
    setRubric((prev) => {
      const next = [...prev.criteria]
      const nextLevels = [...next[critIndex].levels]
      nextLevels[levelIndex] = { ...nextLevels[levelIndex], ...updates }
      next[critIndex] = { ...next[critIndex], levels: nextLevels }
      return { ...prev, criteria: next }
    })
  }

  const handleUpdateLatePenalty = (updates: Partial<LatePenaltyConfig>) => {
    setRubric((prev) => ({
      ...prev,
      latePenaltyConfig: {
        ...(prev.latePenaltyConfig || DEFAULT_LATE_PENALTY_CONFIG),
        ...updates,
      },
    }))
  }

  const handleExportJSON = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(rubric, null, 2))
    const downloadAnchor = document.createElement('a')
    downloadAnchor.setAttribute('href', dataStr)
    downloadAnchor.setAttribute('download', `${rubric.title.toLowerCase().replace(/\s+/g, '-')}-rubric.json`)
    document.body.appendChild(downloadAnchor)
    downloadAnchor.click()
    downloadAnchor.remove()
  }

  const handleSave = () => {
    if (onSaveRubric) {
      onSaveRubric(rubric)
    }
    setSavedToast(true)
    setTimeout(() => setSavedToast(false), 2500)
  }

  const activeCriterion = rubric.criteria[activeCriterionIndex] || rubric.criteria[0]

  return (
    <div className="flex flex-col w-full h-full bg-[#f8f8f8] p-6 space-y-6 overflow-y-auto">
      {/* Header & Preset Switcher */}
      <div className={`${LH_CARD} p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4`}>
        <div className="space-y-1">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 bg-black text-white rounded-lg">
              <Award size={20} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-900">Analytical Rubric Studio</h2>
              <p className="text-xs text-gray-500">
                Define multi-criteria grading matrices, weighted analytical competencies, and automated decay rules.
              </p>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Preset Selector */}
          <div className="flex items-center space-x-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5">
            <Sparkles size={14} className="text-amber-500" />
            <span className="text-xs font-semibold text-gray-600">Preset:</span>
            <select
              value={selectedPresetId}
              onChange={(e) => handleApplyPreset(e.target.value)}
              disabled={readOnly}
              aria-label="Rubric preset template selector"
              className="text-xs font-bold bg-transparent text-gray-900 focus:outline-none cursor-pointer"
            >
              {RUBRIC_PRESETS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title.split(' ')[0]} {p.title.split(' ')[1]}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={handleExportJSON}
            className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors border border-gray-200"
            title="Export Rubric Schema (JSON)"
          >
            <Download size={15} />
          </button>

          {!readOnly && (
            <button
              onClick={handleSave}
              className={`${LH_PRIMARY_BUTTON} flex items-center space-x-2`}
            >
              <Save size={14} />
              <span>Save Rubric</span>
            </button>
          )}

          {savedToast && (
            <span className="text-xs font-semibold text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-full animate-fade-in flex items-center gap-1">
              <CheckCircle2 size={13} /> Rubric Saved!
            </span>
          )}
        </div>
      </div>

      {/* Rubric Metadata & Weight Status Bar */}
      <div className={`${LH_CARD} p-5 space-y-4`}>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="md:col-span-2 space-y-1">
            <label className="text-xs font-bold text-gray-700 uppercase tracking-wider">Rubric Title</label>
            <input
              type="text"
              value={rubric.title}
              onChange={(e) => setRubric((prev) => ({ ...prev, title: e.target.value }))}
              disabled={readOnly}
              className="w-full text-sm font-semibold px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:bg-white focus:outline-none focus:ring-2 focus:ring-black/10"
              placeholder="e.g. Science Lab Report Rubric"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-bold text-gray-700 uppercase tracking-wider">Scoring Scale</label>
            <div className="flex items-center space-x-2 bg-gray-50 border border-gray-200 rounded-lg p-1">
              <button
                type="button"
                onClick={() => setRubric((prev) => ({ ...prev, scaleType: 'percentage' }))}
                className={`flex-1 py-1.5 text-xs font-bold rounded-md transition-all ${
                  rubric.scaleType === 'percentage' ? 'bg-black text-white' : 'text-gray-600 hover:text-black'
                }`}
              >
                100% Weighted
              </button>
              <button
                type="button"
                onClick={() => setRubric((prev) => ({ ...prev, scaleType: 'points' }))}
                className={`flex-1 py-1.5 text-xs font-bold rounded-md transition-all ${
                  rubric.scaleType === 'points' ? 'bg-black text-white' : 'text-gray-600 hover:text-black'
                }`}
              >
                Raw Points
              </button>
            </div>
          </div>
        </div>

        {/* Weight Allocation Bar */}
        <div className="pt-2 border-t border-gray-100 flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-1.5">
              <Layers size={15} className="text-gray-500" />
              <span className="text-xs font-bold text-gray-700">Total Criteria Weight:</span>
            </div>
            <div
              className={`px-2.5 py-0.5 rounded-full text-xs font-extrabold flex items-center gap-1 ${
                isWeightValid
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  : 'bg-amber-50 text-amber-700 border border-amber-200'
              }`}
            >
              {isWeightValid ? <CheckCircle2 size={12} /> : <AlertCircle size={12} />}
              <span>{totalWeight}% / 100%</span>
            </div>
            {!isWeightValid && (
              <span className="text-xs text-amber-600 font-medium">
                Weights must sum to 100% (currently {totalWeight > 100 ? `+${totalWeight - 100}%` : `-${100 - totalWeight}%`})
              </span>
            )}
          </div>

          <button
            onClick={() => setShowLateSettings(!showLateSettings)}
            className="text-xs font-semibold text-gray-600 hover:text-black flex items-center space-x-1.5 self-start md:self-auto"
          >
            <Clock size={13} className="text-rose-500" />
            <span>Late Decay Policy: {rubric.latePenaltyConfig?.enabled ? `-${rubric.latePenaltyConfig.decayPercentPer24h}% / 24h` : 'Disabled'}</span>
            <ChevronDown size={12} className={`transition-transform ${showLateSettings ? 'rotate-180' : ''}`} />
          </button>
        </div>

        {/* Collapsible Late Penalty Configuration Box */}
        {showLateSettings && (
          <div className="bg-rose-50/50 border border-rose-100 rounded-xl p-4 mt-2 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Clock size={16} className="text-rose-600" />
                <h4 className="text-xs font-bold text-rose-950 uppercase tracking-wider">
                  Automated Late Penalty Decay Policy
                </h4>
              </div>
              <label className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={rubric.latePenaltyConfig?.enabled ?? true}
                  onChange={(e) => handleUpdateLatePenalty({ enabled: e.target.checked })}
                  disabled={readOnly}
                  className="rounded border-gray-300 text-black focus:ring-black"
                />
                <span className="text-xs font-bold text-gray-800">Enable Decay</span>
              </label>
            </div>

            {rubric.latePenaltyConfig?.enabled && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
                <div className="bg-white p-2.5 rounded-lg border border-rose-100">
                  <label className="text-[11px] font-bold text-gray-600 block mb-1">Decay Rate (% / 24h)</label>
                  <div className="flex items-center space-x-1">
                    <input
                      type="number"
                      min="0"
                      max="100"
                      value={rubric.latePenaltyConfig?.decayPercentPer24h ?? 5}
                      onChange={(e) => handleUpdateLatePenalty({ decayPercentPer24h: Number(e.target.value) })}
                      disabled={readOnly}
                      className="w-full text-xs font-bold px-2 py-1 bg-gray-50 border border-gray-200 rounded focus:outline-none"
                    />
                    <span className="text-xs font-bold text-gray-500">%</span>
                  </div>
                </div>

                <div className="bg-white p-2.5 rounded-lg border border-rose-100">
                  <label className="text-[11px] font-bold text-gray-600 block mb-1">Max Penalty Cap (%)</label>
                  <div className="flex items-center space-x-1">
                    <input
                      type="number"
                      min="0"
                      max="100"
                      value={rubric.latePenaltyConfig?.maxPenaltyPercent ?? 50}
                      onChange={(e) => handleUpdateLatePenalty({ maxPenaltyPercent: Number(e.target.value) })}
                      disabled={readOnly}
                      className="w-full text-xs font-bold px-2 py-1 bg-gray-50 border border-gray-200 rounded focus:outline-none"
                    />
                    <span className="text-xs font-bold text-gray-500">%</span>
                  </div>
                </div>

                <div className="bg-white p-2.5 rounded-lg border border-rose-100">
                  <label className="text-[11px] font-bold text-gray-600 block mb-1">Grace Period (Hours)</label>
                  <div className="flex items-center space-x-1">
                    <input
                      type="number"
                      min="0"
                      max="72"
                      value={rubric.latePenaltyConfig?.gracePeriodHours ?? 1}
                      onChange={(e) => handleUpdateLatePenalty({ gracePeriodHours: Number(e.target.value) })}
                      disabled={readOnly}
                      className="w-full text-xs font-bold px-2 py-1 bg-gray-50 border border-gray-200 rounded focus:outline-none"
                    />
                    <span className="text-xs font-bold text-gray-500">hrs</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Main Criteria Builder Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Criteria Master List */}
        <div className="lg:col-span-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-gray-700 uppercase tracking-wider">
              Analytical Criteria ({rubric.criteria.length})
            </span>
            {!readOnly && (
              <button
                onClick={handleAddCriterion}
                className="text-xs font-bold text-black hover:text-gray-700 flex items-center space-x-1 bg-white px-2.5 py-1 rounded-lg nice-shadow transition-colors"
              >
                <Plus size={13} />
                <span>Add Criterion</span>
              </button>
            )}
          </div>

          <div className="space-y-2.5">
            {rubric.criteria.map((crit, idx) => {
              const isActive = idx === activeCriterionIndex
              return (
                <div
                  key={crit.id}
                  onClick={() => setActiveCriterionIndex(idx)}
                  className={`cursor-pointer rounded-xl p-3.5 transition-all ${
                    isActive
                      ? 'bg-black text-white nice-shadow ring-2 ring-black/20'
                      : 'bg-white hover:bg-gray-50 text-gray-900 nice-shadow'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-1 min-w-0 flex-1">
                      <div className="flex items-center space-x-2">
                        <span
                          className={`text-[10px] font-mono px-1.5 py-0.5 rounded font-bold ${
                            isActive ? 'bg-white/20 text-white' : 'bg-gray-100 text-gray-700'
                          }`}
                        >
                          C{idx + 1}
                        </span>
                        <h4 className="text-xs font-bold truncate">{crit.title || 'Untitled Criterion'}</h4>
                      </div>
                      <p className={`text-[11px] line-clamp-1 ${isActive ? 'text-gray-300' : 'text-gray-500'}`}>
                        {crit.description}
                      </p>
                    </div>

                    <div className="flex items-center space-x-2 shrink-0">
                      <span
                        className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${
                          isActive ? 'bg-white text-black' : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {crit.weight}%
                      </span>

                      {!readOnly && (
                        <div
                          className="flex items-center space-x-0.5"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <button
                            onClick={() => handleMoveCriterion(idx, 'up')}
                            disabled={idx === 0}
                            className={`p-1 rounded hover:bg-white/20 disabled:opacity-20 ${
                              isActive ? 'text-white' : 'text-gray-400'
                            }`}
                            title="Move Up"
                          >
                            <ChevronUp size={13} />
                          </button>
                          <button
                            onClick={() => handleMoveCriterion(idx, 'down')}
                            disabled={idx === rubric.criteria.length - 1}
                            className={`p-1 rounded hover:bg-white/20 disabled:opacity-20 ${
                              isActive ? 'text-white' : 'text-gray-400'
                            }`}
                            title="Move Down"
                          >
                            <ChevronDown size={13} />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Right Column: Active Criterion & 4 Level Descriptors Matrix */}
        <div className="lg:col-span-8 space-y-4">
          {activeCriterion ? (
            <div className={`${LH_CARD} p-6 space-y-5`}>
              {/* Criterion Header Fields */}
              <div className="flex items-center justify-between border-b border-gray-100 pb-4">
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-mono font-bold bg-black text-white px-2 py-1 rounded">
                    Criterion {activeCriterionIndex + 1} of {rubric.criteria.length}
                  </span>
                  <span className="text-xs font-bold text-gray-400">|</span>
                  <span className="text-xs font-semibold text-gray-600">Multi-Level Analytical Descriptors</span>
                </div>

                {!readOnly && (
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => handleDuplicateCriterion(activeCriterionIndex)}
                      className="p-1.5 text-gray-500 hover:text-black hover:bg-gray-100 rounded-lg text-xs font-semibold flex items-center space-x-1"
                      title="Duplicate Criterion"
                    >
                      <Copy size={13} />
                      <span className="hidden sm:inline">Duplicate</span>
                    </button>
                    {rubric.criteria.length > 1 && (
                      <button
                        onClick={() => handleDeleteCriterion(activeCriterionIndex)}
                        className="p-1.5 text-rose-600 hover:bg-rose-50 rounded-lg text-xs font-semibold flex items-center space-x-1"
                        title="Delete Criterion"
                      >
                        <Trash2 size={13} />
                        <span className="hidden sm:inline">Delete</span>
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Title & Weight Fields */}
              <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
                <div className="sm:col-span-8 space-y-1">
                  <label className="text-xs font-bold text-gray-700">Criterion Name</label>
                  <input
                    type="text"
                    value={activeCriterion.title}
                    onChange={(e) => handleUpdateCriterion(activeCriterionIndex, { title: e.target.value })}
                    disabled={readOnly}
                    className="w-full text-xs font-semibold px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:bg-white focus:outline-none focus:ring-2 focus:ring-black/10"
                    placeholder="e.g. Hypothesis & Theoretical Framework"
                  />
                </div>

                <div className="sm:col-span-2 space-y-1">
                  <label className="text-xs font-bold text-gray-700">Weight (%)</label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={activeCriterion.weight}
                    onChange={(e) => {
                      const newWeight = Number(e.target.value) || 0
                      handleUpdateCriterion(activeCriterionIndex, {
                        weight: newWeight,
                        maxPoints: newWeight,
                      })
                    }}
                    disabled={readOnly}
                    className="w-full text-xs font-bold px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:bg-white focus:outline-none"
                  />
                </div>

                <div className="sm:col-span-2 space-y-1">
                  <label className="text-xs font-bold text-gray-700">Max Points</label>
                  <input
                    type="number"
                    min="1"
                    value={activeCriterion.maxPoints}
                    onChange={(e) =>
                      handleUpdateCriterion(activeCriterionIndex, { maxPoints: Number(e.target.value) || 1 })
                    }
                    disabled={readOnly}
                    className="w-full text-xs font-bold px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:bg-white focus:outline-none"
                  />
                </div>
              </div>

              {/* Description Field */}
              <div className="space-y-1">
                <label className="text-xs font-bold text-gray-700">Criterion Description / Core Competency</label>
                <textarea
                  rows={2}
                  value={activeCriterion.description}
                  onChange={(e) => handleUpdateCriterion(activeCriterionIndex, { description: e.target.value })}
                  disabled={readOnly}
                  className="w-full text-xs font-normal px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:bg-white focus:outline-none"
                  placeholder="Outline the core skill, analytical principle, or standard measured by this criterion."
                />
              </div>

              {/* 4 Level Descriptors Matrix (Exemplary, Proficient, Developing, Novice) */}
              <div className="space-y-3 pt-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-gray-800 uppercase tracking-wider flex items-center space-x-1.5">
                    <Award size={14} className="text-indigo-600" />
                    <span>Performance Level Descriptors (4-Level Matrix)</span>
                  </span>
                  <span className="text-[11px] text-gray-400 font-medium">
                    Shortcut Keys 1 (Exemplary) to 4 (Novice) in SpeedGrader
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                  {activeCriterion.levels.map((level, lvlIdx) => {
                    const levelColors: Record<string, { badge: string; border: string; key: string }> = {
                      exemplary: { badge: 'bg-emerald-50 text-emerald-700', border: 'border-emerald-200', key: '1' },
                      proficient: { badge: 'bg-blue-50 text-blue-700', border: 'border-blue-200', key: '2' },
                      developing: { badge: 'bg-amber-50 text-amber-700', border: 'border-amber-200', key: '3' },
                      novice: { badge: 'bg-rose-50 text-rose-700', border: 'border-rose-200', key: '4' },
                    }
                    const style = levelColors[level.id] || { badge: 'bg-gray-100 text-gray-700', border: 'border-gray-200', key: `${lvlIdx + 1}` }

                    return (
                      <div
                        key={level.id}
                        className={`rounded-xl p-3.5 border ${style.border} bg-white nice-shadow space-y-2.5`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-2">
                            <span className="text-[10px] font-mono font-extrabold bg-black text-white px-1.5 py-0.5 rounded">
                              Key {style.key}
                            </span>
                            <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${style.badge}`}>
                              {level.name}
                            </span>
                          </div>

                          <div className="flex items-center space-x-1 text-xs font-bold text-gray-700">
                            <input
                              type="number"
                              value={level.points}
                              onChange={(e) =>
                                handleUpdateLevel(activeCriterionIndex, lvlIdx, {
                                  points: Number(e.target.value) || 0,
                                })
                              }
                              disabled={readOnly}
                              aria-label={`${level.name} points`}
                              className="w-12 text-center font-bold px-1 py-0.5 bg-gray-50 border border-gray-200 rounded focus:outline-none"
                            />
                            <span>pts</span>
                          </div>
                        </div>

                        <div>
                          <textarea
                            rows={3}
                            value={level.description}
                            onChange={(e) =>
                              handleUpdateLevel(activeCriterionIndex, lvlIdx, {
                                description: e.target.value,
                              })
                            }
                            disabled={readOnly}
                            aria-label={`${level.name} detailed performance benchmark descriptor`}
                            className="w-full text-xs text-gray-600 bg-gray-50 border border-gray-100 rounded-lg p-2 focus:bg-white focus:outline-none focus:ring-1 focus:ring-black/10 resize-none"
                            placeholder="Detailed performance benchmark descriptor..."
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-xl p-12 text-center nice-shadow text-gray-400">
              Select or add a criterion to begin configuring analytical level descriptors.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
