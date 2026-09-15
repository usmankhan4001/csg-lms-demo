import { FormulaItem } from './types'

export const STEM_FORMULA_PRESETS: FormulaItem[] = [
  // Mathematics
  {
    id: 'math-quad',
    category: 'Mathematics',
    title: 'Quadratic Formula',
    formula: 'x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}',
    description: 'Roots of a quadratic equation ax² + bx + c = 0',
  },
  {
    id: 'math-pyth',
    category: 'Mathematics',
    title: 'Pythagorean Theorem',
    formula: 'a^2 + b^2 = c^2',
    description: 'Relationship between the sides of a right triangle',
  },
  {
    id: 'math-eul',
    category: 'Mathematics',
    title: "Euler's Identity",
    formula: 'e^{i\\pi} + 1 = 0',
    description: 'Fundamental link between exponential and trigonometric functions',
  },
  {
    id: 'math-trig-id',
    category: 'Mathematics',
    title: 'Fundamental Trigonometric Identity',
    formula: '\\sin^2(\\theta) + \\cos^2(\\theta) = 1',
    description: 'Pythagorean trigonometric identity',
  },
  {
    id: 'math-deriv-prod',
    category: 'Mathematics',
    title: 'Product Rule (Calculus)',
    formula: '\\frac{d}{dx}[u \\cdot v] = u\'v + uv\'',
    description: 'Derivative of the product of two functions',
  },
  {
    id: 'math-deriv-chain',
    category: 'Mathematics',
    title: 'Chain Rule (Calculus)',
    formula: '\\frac{d}{dx}[f(g(x))] = f\'(g(x)) \\cdot g\'(x)',
    description: 'Derivative of composite functions',
  },

  // Physics
  {
    id: 'phys-newton2',
    category: 'Physics',
    title: "Newton's Second Law of Motion",
    formula: '\\vec{F} = m\\vec{a}',
    description: 'Force equals mass times acceleration',
  },
  {
    id: 'phys-kinematics1',
    category: 'Physics',
    title: 'Kinematics: Velocity-Displacement',
    formula: 'v^2 = u^2 + 2as',
    description: 'Uniform acceleration without explicit time parameter',
  },
  {
    id: 'phys-grav',
    category: 'Physics',
    title: 'Universal Law of Gravitation',
    formula: 'F = G \\frac{m_1 m_2}{r^2}',
    description: 'Gravitational attraction between two point masses',
  },
  {
    id: 'phys-ohm',
    category: 'Physics',
    title: "Ohm's Law",
    formula: 'V = I \\cdot R',
    description: 'Voltage equals current times resistance',
  },
  {
    id: 'phys-einstein',
    category: 'Physics',
    title: 'Mass-Energy Equivalence',
    formula: 'E = mc^2',
    description: 'Equivalence of relativistic mass and energy',
  },
  {
    id: 'phys-work-energy',
    category: 'Physics',
    title: 'Kinetic Energy & Work',
    formula: 'KE = \\frac{1}{2}mv^2, \\quad W = \\Delta KE',
    description: 'Kinetic energy and work-energy theorem',
  },

  // Chemistry
  {
    id: 'chem-ideal-gas',
    category: 'Chemistry',
    title: 'Ideal Gas Law',
    formula: 'PV = nRT',
    description: 'Pressure, volume, moles, gas constant, and absolute temperature',
  },
  {
    id: 'chem-ph',
    category: 'Chemistry',
    title: 'pH Definition',
    formula: '\\text{pH} = -\\log_{10}[H^+]',
    description: 'Hydrogen ion concentration measure of acidity/basicity',
  },
  {
    id: 'chem-nernst',
    category: 'Chemistry',
    title: 'Nernst Equation (Electrochemistry)',
    formula: 'E = E^\\circ - \\frac{RT}{nF} \\ln Q',
    description: 'Cell potential under non-standard conditions',
  },
  {
    id: 'chem-gibbs',
    category: 'Chemistry',
    title: "Gibbs Free Energy",
    formula: '\\Delta G = \\Delta H - T\\Delta S',
    description: 'Thermodynamic criterion for reaction spontaneity',
  },

  // Statistics
  {
    id: 'stat-z-score',
    category: 'Statistics',
    title: 'Standard Normal Z-Score',
    formula: 'Z = \\frac{X - \\mu}{\\sigma}',
    description: 'Standardizing raw scores relative to mean and standard deviation',
  },
  {
    id: 'stat-bayes',
    category: 'Statistics',
    title: "Bayes' Theorem",
    formula: 'P(A|B) = \\frac{P(B|A)P(A)}{P(B)}',
    description: 'Conditional probability update given new evidence',
  },
  {
    id: 'stat-cronbach',
    category: 'Statistics',
    title: "Cronbach's Alpha (Test Reliability)",
    formula: '\\alpha = \\frac{K}{K - 1} \\left( 1 - \\frac{\\sum \\sigma_j^2}{\\sigma_{\\text{total}}^2} \\right)',
    description: 'Internal consistency reliability index across exam items',
  },
  {
    id: 'stat-irt-2pl',
    category: 'Statistics',
    title: 'IRT 2-Parameter Logistic Model (2PL)',
    formula: 'P(\\theta) = \\frac{1}{1 + e^{-\\alpha(\\theta - \\beta)}}',
    description: 'Probability of correct response given ability θ, discrimination α, and difficulty β',
  },

  // Computer Science
  {
    id: 'cs-shannon',
    category: 'Computer Science',
    title: 'Shannon Entropy (Information Theory)',
    formula: 'H(X) = -\\sum_{i=1}^n P(x_i) \\log_2 P(x_i)',
    description: 'Expected information content / uncertainty in a discrete random variable',
  },
  {
    id: 'cs-binary-search',
    category: 'Computer Science',
    title: 'Binary Search Time Complexity',
    formula: 'T(n) = \\mathcal{O}(\\log_2 n)',
    description: 'Logarithmic search time in sorted arrays',
  },
  {
    id: 'cs-master-theorem',
    category: 'Computer Science',
    title: 'Master Theorem for Divide-and-Conquer',
    formula: 'T(n) = a T(n/b) + f(n)',
    description: 'Asymptotic complexity of recursive recurrence relations',
  },
]
