// Pure cost helpers — no React imports (Sacred Invariant 5).
// Per-image estimates in USD; MUST match src/lantern/gemini.py's table
// (Verify B checks the seam). Plan-time pricing for gemini-3-pro-image-preview:
// ~$0.134 per 1K/2K image, ~$0.24 at 4K.

import type { SlideSize } from './types'

export const COST_PER_IMAGE_USD: Record<SlideSize, number> = {
  '1K': 0.134,
  '2K': 0.134,
  '4K': 0.24,
}

export function estimateDeckCost(slideCount: number, size: SlideSize): number {
  return slideCount * COST_PER_IMAGE_USD[size]
}

export function formatUsd(n: number): string {
  return `$${n.toFixed(2)}`
}
