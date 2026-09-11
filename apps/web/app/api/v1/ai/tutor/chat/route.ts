import { NextRequest, NextResponse } from 'next/server'

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const { message, context, hintType, history } = body

    // Socratic response logic generator
    let socraticResponse = ''

    if (hintType === 'concept') {
      socraticResponse = `💡 **Concept Clue:** Think about the underlying physical or mathematical law at play. What is the fundamental conservation principle (like energy or momentum) that applies when no external torque is exerted?`
    } else if (hintType === 'formula') {
      socraticResponse = `📐 **Formula / Rule:** Consider the equation: \n$$\\tau = I\\alpha = \\frac{dL}{dt}$$\nWhere $\\tau$ is net torque, $I$ is moment of inertia, and $\\alpha$ is angular acceleration. How can you relate this to the linear equivalent $F = ma$?`
    } else if (hintType === 'example') {
      socraticResponse = `🔍 **Worked Example Thought:** Imagine a spinning figure skater pulling their arms inward. Their moment of inertia decreases, so what must happen to their spin rate to conserve angular momentum? How does this map to our problem?`
    } else if (message) {
      const lower = message.toLowerCase()
      if (lower.includes('formula') || lower.includes('equation')) {
        socraticResponse = `Let's break down the mathematical formulation. If we look at the rate of change of angular momentum $\\frac{dL}{dt}$, what variable remains constant in an isolated system? How would you set up the balance equation?`
      } else if (lower.includes('code') || lower.includes('python') || lower.includes('bug') || lower.includes('error')) {
        socraticResponse = `Let's inspect the code logic together. What is the expected return value for your base condition, and what is currently being passed into the recursive call? Try tracing it with an input array of size 1.`
      } else if (lower.includes('torque') || lower.includes('inertia') || lower.includes('physics')) {
        socraticResponse = `Great observation! Notice how the distribution of mass relative to the axis of rotation changes $I = \\sum m_i r_i^2$. If the distance from the pivot doubles, what factor does the rotational inertia increase by?`
      } else {
        socraticResponse = `That's an insightful question about **${message.slice(0, 40)}...**! To help you deduce the answer yourself: what happens to the system if you isolate the primary variable and hold all other parameters constant? What would be your first step?`
      }
    } else {
      socraticResponse = `I am your Socratic AI Tutor. Ask me any question about this lesson, or pick one of the hint tiers above to guide your reasoning!`
    }

    // Return a streaming text response with chunked delay simulation for high realism
    const encoder = new TextEncoder()
    const stream = new ReadableStream({
      async start(controller) {
        const words = socraticResponse.split(' ')
        for (let i = 0; i < words.length; i++) {
          const chunk = (i === 0 ? '' : ' ') + words[i]
          controller.enqueue(encoder.encode(chunk))
          // small delay to emulate real-time LLM token streaming
          await new Promise((resolve) => setTimeout(resolve, 35))
        }
        controller.close()
      },
    })

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
        'Cache-Control': 'no-cache',
        'Transfer-Encoding': 'chunked',
      },
    })
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to generate Socratic AI response' },
      { status: 500 }
    )
  }
}
