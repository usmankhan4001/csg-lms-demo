'use client'

import React, { useState, useMemo } from 'react'
import {
  X,
  Search,
  BookOpen,
  Copy,
  Check,
  Filter,
  Atom,
  Binary,
  Calculator,
  Sigma,
  FlaskConical,
} from 'lucide-react'
import { FormulaItem } from './types'
import { STEM_FORMULA_PRESETS } from './formulaPresets'

interface FormulaReferenceModalProps {
  isOpen: boolean
  onClose: () => void
}

type FormulaCategory = 'All' | 'Mathematics' | 'Physics' | 'Chemistry' | 'Statistics' | 'Computer Science'

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  Mathematics: <Calculator className="w-4 h-4 text-blue-400" />,
  Physics: <Atom className="w-4 h-4 text-purple-400" />,
  Chemistry: <FlaskConical className="w-4 h-4 text-emerald-400" />,
  Statistics: <Sigma className="w-4 h-4 text-amber-400" />,
  'Computer Science': <Binary className="w-4 h-4 text-cyan-400" />,
}

export const FormulaReferenceModal: React.FC<FormulaReferenceModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [selectedCategory, setSelectedCategory] = useState<FormulaCategory>('All')
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const categories: FormulaCategory[] = [
    'All',
    'Mathematics',
    'Physics',
    'Chemistry',
    'Statistics',
    'Computer Science',
  ]

  const filteredFormulas = useMemo(() => {
    return STEM_FORMULA_PRESETS.filter((item) => {
      const matchesCat = selectedCategory === 'All' || item.category === selectedCategory
      const q = searchQuery.toLowerCase().trim()
      const matchesSearch =
        !q ||
        item.title.toLowerCase().includes(q) ||
        item.formula.toLowerCase().includes(q) ||
        (item.description && item.description.toLowerCase().includes(q)) ||
        item.category.toLowerCase().includes(q)
      return matchesCat && matchesSearch
    })
  }, [searchQuery, selectedCategory])

  if (!isOpen) return null

  const handleCopyFormula = (id: string, formula: string) => {
    navigator.clipboard.writeText(formula)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 1500)
  }

  // Format LaTeX formula into clean human-readable text for quick reference
  const renderFormulaText = (latex: string) => {
    return latex
      .replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, '($1 / $2)')
      .replace(/\\sqrt\{([^}]+)\}/g, '√($1)')
      .replace(/\\pm/g, '±')
      .replace(/\\cdot/g, '·')
      .replace(/\\vec\{([^}]+)\}/g, '$1')
      .replace(/\\theta/g, 'θ')
      .replace(/\\pi/g, 'π')
      .replace(/\\alpha/g, 'α')
      .replace(/\\beta/g, 'β')
      .replace(/\\sigma/g, 'σ')
      .replace(/\\mu/g, 'μ')
      .replace(/\\Delta/g, 'Δ')
      .replace(/\\sum/g, '∑')
      .replace(/\\mathcal\{O\}/g, 'O')
      .replace(/\\quad/g, ' ')
      .replace(/\\circ/g, '°')
      .replace(/\\ln/g, 'ln')
      .replace(/\\log_2/g, 'log₂')
      .replace(/\\log_\{10\}/g, 'log₁₀')
      .replace(/\\text\{([^}]+)\}/g, '$1')
      .replace(/\{|\}/g, '')
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
      <div className="w-full max-w-2xl bg-neutral-900 border border-neutral-700/80 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh] text-neutral-100 animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 bg-neutral-800/80 border-b border-neutral-700/60">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-purple-500/20 text-purple-400">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-base tracking-wide text-neutral-100">STEM Formula Reference Sheet</h3>
              <p className="text-xs text-neutral-400">Standard CBT reference sheet for mathematics and sciences</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-neutral-400 hover:text-white rounded-lg hover:bg-neutral-700 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search & Category Filter */}
        <div className="p-4 bg-neutral-900/90 border-b border-neutral-800 space-y-3">
          <div className="relative">
            <Search className="w-4 h-4 text-neutral-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search formulas by name, concept, or variable..."
              className="w-full pl-10 pr-4 py-2 bg-neutral-950 border border-neutral-700 rounded-xl text-sm text-neutral-100 placeholder-neutral-500 focus:outline-hidden focus:border-purple-500 transition-colors"
            />
          </div>

          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-3 py-1.5 rounded-lg font-medium whitespace-nowrap transition-colors flex items-center gap-1.5 ${
                  selectedCategory === cat
                    ? 'bg-purple-600 text-white shadow-xs'
                    : 'bg-neutral-800 text-neutral-400 hover:bg-neutral-700 hover:text-neutral-200'
                }`}
              >
                {cat !== 'All' && CATEGORY_ICONS[cat]}
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* Formula Cards List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {filteredFormulas.length === 0 ? (
            <div className="text-center py-12 text-neutral-500">
              <BookOpen className="w-10 h-10 mx-auto mb-2 opacity-40" />
              <p className="text-sm font-medium">No formulas found matching "{searchQuery}"</p>
              <p className="text-xs text-neutral-600 mt-1">Try searching for a different term or select "All"</p>
            </div>
          ) : (
            filteredFormulas.map((item) => (
              <div
                key={item.id}
                className="p-4 rounded-xl bg-neutral-950/80 border border-neutral-800 hover:border-neutral-700 transition-colors flex flex-col gap-2 relative group"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs px-2 py-0.5 rounded-md bg-neutral-800 text-neutral-300 font-medium">
                        {item.category}
                      </span>
                      <h4 className="font-semibold text-sm text-neutral-100">{item.title}</h4>
                    </div>
                    {item.description && (
                      <p className="text-xs text-neutral-400 mt-1">{item.description}</p>
                    )}
                  </div>
                  <button
                    onClick={() => handleCopyFormula(item.id, renderFormulaText(item.formula))}
                    className="p-1.5 text-neutral-400 hover:text-neutral-200 rounded-md bg-neutral-900 border border-neutral-800 opacity-80 group-hover:opacity-100 transition-all"
                    title="Copy formula"
                  >
                    {copiedId === item.id ? (
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>

                {/* Formula Display Box */}
                <div className="mt-1 px-4 py-3 bg-neutral-900/90 rounded-lg border border-neutral-800/80 font-mono text-base text-purple-300 tracking-wide overflow-x-auto select-all">
                  {renderFormulaText(item.formula)}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 bg-neutral-800/60 border-t border-neutral-700/60 flex items-center justify-between text-xs text-neutral-400">
          <span>{filteredFormulas.length} formulas available</span>
          <span>Press ESC or click close to return to exam</span>
        </div>
      </div>
    </div>
  )
}
