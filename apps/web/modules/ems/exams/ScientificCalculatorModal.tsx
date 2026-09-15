'use client'

import React, { useState, useCallback } from 'react'
import {
  X,
  RotateCcw,
  Delete,
  Calculator as CalcIcon,
  Maximize2,
  Minimize2,
  Copy,
  Check,
} from 'lucide-react'

interface ScientificCalculatorModalProps {
  isOpen: boolean
  onClose: () => void
}

export const ScientificCalculatorModal: React.FC<ScientificCalculatorModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [display, setDisplay] = useState<string>('0')
  const [equation, setEquation] = useState<string>('')
  const [isRad, setIsRad] = useState<boolean>(true)
  const [memory, setMemory] = useState<number>(0)
  const [hasMemory, setHasMemory] = useState<boolean>(false)
  const [history, setHistory] = useState<string[]>([])
  const [copied, setCopied] = useState<boolean>(false)

  if (!isOpen) return null

  const handleDigit = (digit: string) => {
    setDisplay((prev) => (prev === '0' || prev === 'Error' ? digit : prev + digit))
  }

  const handleOperator = (op: string) => {
    setEquation(display + ' ' + op + ' ')
    setDisplay('0')
  }

  const handleClear = () => {
    setDisplay('0')
    setEquation('')
  }

  const handleBackspace = () => {
    setDisplay((prev) => {
      if (prev.length <= 1 || prev === 'Error') return '0'
      return prev.slice(0, -1)
    })
  }

  const handleScientific = (funcName: string) => {
    const val = parseFloat(display)
    if (isNaN(val)) return

    let result = 0
    const toRad = isRad ? val : (val * Math.PI) / 180

    switch (funcName) {
      case 'sin':
        result = Math.sin(toRad)
        break
      case 'cos':
        result = Math.cos(toRad)
        break
      case 'tan':
        result = Math.tan(toRad)
        break
      case 'asin':
        result = isRad ? Math.asin(val) : (Math.asin(val) * 180) / Math.PI
        break
      case 'acos':
        result = isRad ? Math.acos(val) : (Math.acos(val) * 180) / Math.PI
        break
      case 'atan':
        result = isRad ? Math.atan(val) : (Math.atan(val) * 180) / Math.PI
        break
      case 'sqrt':
        result = val < 0 ? NaN : Math.sqrt(val)
        break
      case 'cbrt':
        result = Math.cbrt(val)
        break
      case 'sq':
        result = val * val
        break
      case 'cube':
        result = val * val * val
        break
      case 'ln':
        result = val <= 0 ? NaN : Math.log(val)
        break
      case 'log10':
        result = val <= 0 ? NaN : Math.log10(val)
        break
      case 'exp':
        result = Math.exp(val)
        break
      case 'inv':
        result = val === 0 ? NaN : 1 / val
        break
      case 'fact':
        if (val < 0 || !Number.isInteger(val) || val > 170) {
          result = NaN
        } else {
          let f = 1
          for (let i = 2; i <= val; i++) f *= i
          result = f
        }
        break
      case 'negate':
        result = -val
        break
      case 'pct':
        result = val / 100
        break
      default:
        return
    }

    if (isNaN(result) || !isFinite(result)) {
      setDisplay('Error')
    } else {
      const formatted = String(Number(result.toFixed(8)))
      setHistory((prev) => [`${funcName}(${display}) = ${formatted}`, ...prev.slice(0, 5)])
      setDisplay(formatted)
    }
  }

  const handleConstant = (c: 'pi' | 'e') => {
    const val = c === 'pi' ? Math.PI : Math.E
    setDisplay(String(Number(val.toFixed(8))))
  }

  const handleEqual = () => {
    if (!equation) return
    const fullExpr = equation + display
    try {
      // Safe arithmetic evaluator for basic expressions
      const sanitized = fullExpr
        .replace(/×/g, '*')
        .replace(/÷/g, '/')
        .replace(/−/g, '-')
      
      // Basic expression token calculation
      const parts = sanitized.trim().split(/\s+/)
      if (parts.length >= 3) {
        const a = parseFloat(parts[0])
        const op = parts[1]
        const b = parseFloat(parts[2])
        let res = 0
        if (op === '+') res = a + b
        else if (op === '-' || op === '−') res = a - b
        else if (op === '*' || op === '×') res = a * b
        else if (op === '/' || op === '÷') res = b === 0 ? NaN : a / b
        else if (op === '^') res = Math.pow(a, b)
        else if (op === '%') res = a % b
        else res = b

        if (isNaN(res) || !isFinite(res)) {
          setDisplay('Error')
        } else {
          const formatted = String(Number(res.toFixed(8)))
          setHistory((prev) => [`${fullExpr} = ${formatted}`, ...prev.slice(0, 5)])
          setDisplay(formatted)
          setEquation('')
        }
      }
    } catch {
      setDisplay('Error')
    }
  }

  const handleMemory = (action: 'MC' | 'MR' | 'M+' | 'M-') => {
    const val = parseFloat(display) || 0
    if (action === 'MC') {
      setMemory(0)
      setHasMemory(false)
    } else if (action === 'MR') {
      setDisplay(String(memory))
    } else if (action === 'M+') {
      setMemory((prev) => prev + val)
      setHasMemory(true)
    } else if (action === 'M-') {
      setMemory((prev) => prev - val)
      setHasMemory(true)
    }
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(display)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
      <div className="w-full max-w-lg bg-neutral-900 border border-neutral-700/80 rounded-2xl shadow-2xl overflow-hidden flex flex-col text-neutral-100 animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 bg-neutral-800/80 border-b border-neutral-700/60">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-blue-500/20 text-blue-400">
              <CalcIcon className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-sm tracking-wide text-neutral-100">Scientific Calculator</h3>
              <p className="text-[11px] text-neutral-400">Approved CBT Examination Tool</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsRad((prev) => !prev)}
              className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                isRad
                  ? 'bg-blue-600/30 text-blue-300 border border-blue-500/40'
                  : 'bg-amber-600/30 text-amber-300 border border-amber-500/40'
              }`}
              title="Toggle Degrees / Radians"
            >
              {isRad ? 'RAD' : 'DEG'}
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-neutral-400 hover:text-white rounded-lg hover:bg-neutral-700 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Display Screen */}
        <div className="px-5 py-4 bg-neutral-950 flex flex-col justify-end border-b border-neutral-800 relative">
          <div className="flex items-center justify-between text-xs text-neutral-500 h-5 font-mono">
            <span>{hasMemory ? `M = ${memory}` : ''}</span>
            <span className="truncate">{equation}</span>
          </div>
          <div className="flex items-center justify-between mt-1">
            <span className="text-3xl font-mono font-bold tracking-tight text-white overflow-x-auto select-all">
              {display}
            </span>
            <button
              onClick={handleCopy}
              className="p-1.5 text-neutral-400 hover:text-neutral-200 rounded transition-colors ml-2"
              title="Copy result"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Keypad Grid */}
        <div className="p-4 grid grid-cols-5 gap-1.5 bg-neutral-900 text-sm">
          {/* Memory row */}
          <button onClick={() => handleMemory('MC')} className="calc-btn-func">MC</button>
          <button onClick={() => handleMemory('MR')} className="calc-btn-func">MR</button>
          <button onClick={() => handleMemory('M+')} className="calc-btn-func">M+</button>
          <button onClick={() => handleMemory('M-')} className="calc-btn-func">M-</button>
          <button onClick={handleBackspace} className="calc-btn-action text-red-400"><Delete className="w-4 h-4 mx-auto" /></button>

          {/* Row 1 Scientific */}
          <button onClick={() => handleScientific('sin')} className="calc-btn-sci">sin</button>
          <button onClick={() => handleScientific('cos')} className="calc-btn-sci">cos</button>
          <button onClick={() => handleScientific('tan')} className="calc-btn-sci">tan</button>
          <button onClick={handleClear} className="calc-btn-action text-amber-400 font-bold col-span-2">AC</button>

          {/* Row 2 Scientific & numbers */}
          <button onClick={() => handleScientific('asin')} className="calc-btn-sci">sin⁻¹</button>
          <button onClick={() => handleScientific('acos')} className="calc-btn-sci">cos⁻¹</button>
          <button onClick={() => handleScientific('atan')} className="calc-btn-sci">tan⁻¹</button>
          <button onClick={() => handleScientific('sq')} className="calc-btn-sci">x²</button>
          <button onClick={() => handleOperator('/')} className="calc-btn-op">÷</button>

          {/* Row 3 */}
          <button onClick={() => handleScientific('ln')} className="calc-btn-sci">ln</button>
          <button onClick={() => handleScientific('log10')} className="calc-btn-sci">log</button>
          <button onClick={() => handleDigit('7')} className="calc-btn-num">7</button>
          <button onClick={() => handleDigit('8')} className="calc-btn-num">8</button>
          <button onClick={() => handleDigit('9')} className="calc-btn-num">9</button>

          {/* Row 4 */}
          <button onClick={() => handleScientific('sqrt')} className="calc-btn-sci">√x</button>
          <button onClick={() => handleOperator('^')} className="calc-btn-sci">xʸ</button>
          <button onClick={() => handleDigit('4')} className="calc-btn-num">4</button>
          <button onClick={() => handleDigit('5')} className="calc-btn-num">5</button>
          <button onClick={() => handleDigit('6')} className="calc-btn-num">6</button>

          {/* Row 5 */}
          <button onClick={() => handleConstant('pi')} className="calc-btn-sci">π</button>
          <button onClick={() => handleConstant('e')} className="calc-btn-sci">e</button>
          <button onClick={() => handleDigit('1')} className="calc-btn-num">1</button>
          <button onClick={() => handleDigit('2')} className="calc-btn-num">2</button>
          <button onClick={() => handleDigit('3')} className="calc-btn-num">3</button>

          {/* Row 6 */}
          <button onClick={() => handleScientific('fact')} className="calc-btn-sci">n!</button>
          <button onClick={() => handleScientific('negate')} className="calc-btn-sci">±</button>
          <button onClick={() => handleDigit('0')} className="calc-btn-num">0</button>
          <button onClick={() => handleDigit('.')} className="calc-btn-num">.</button>
          <button onClick={handleEqual} className="calc-btn-equal bg-blue-600 hover:bg-blue-500 text-white font-bold">=</button>
        </div>

        {/* Recent Calculation Strip */}
        {history.length > 0 && (
          <div className="px-5 py-2.5 bg-neutral-950 border-t border-neutral-800 text-[11px] text-neutral-400 flex items-center justify-between">
            <span className="text-neutral-500 font-medium">History:</span>
            <span className="font-mono truncate max-w-xs">{history[0]}</span>
          </div>
        )}
      </div>

      <style jsx>{`
        .calc-btn-num {
          background-color: #262626;
          color: #f5f5f5;
          font-weight: 600;
          font-size: 1.05rem;
          padding: 0.65rem 0.25rem;
          border-radius: 0.5rem;
          transition: background-color 0.15s;
        }
        .calc-btn-num:hover {
          background-color: #404040;
        }
        .calc-btn-sci {
          background-color: #1e293b;
          color: #93c5fd;
          font-weight: 500;
          font-size: 0.85rem;
          padding: 0.65rem 0.25rem;
          border-radius: 0.5rem;
          transition: background-color 0.15s;
        }
        .calc-btn-sci:hover {
          background-color: #334155;
        }
        .calc-btn-op {
          background-color: #3b82f6;
          color: white;
          font-weight: bold;
          font-size: 1.1rem;
          padding: 0.65rem 0.25rem;
          border-radius: 0.5rem;
        }
        .calc-btn-op:hover {
          background-color: #2563eb;
        }
        .calc-btn-func {
          background-color: #171717;
          color: #a3a3a3;
          font-size: 0.75rem;
          font-weight: 600;
          padding: 0.45rem 0.25rem;
          border-radius: 0.375rem;
        }
        .calc-btn-func:hover {
          background-color: #262626;
          color: white;
        }
        .calc-btn-action {
          background-color: #171717;
          padding: 0.65rem 0.25rem;
          border-radius: 0.5rem;
        }
        .calc-btn-action:hover {
          background-color: #262626;
        }
        .calc-btn-equal {
          padding: 0.65rem 0.25rem;
          border-radius: 0.5rem;
          font-size: 1.1rem;
        }
      `}</style>
    </div>
  )
}
