// Pure cost helpers — no React imports (Sacred Invariant 5).
// Prices come from config/imageModels.ts (THE painter list), whose numbers
// MUST match src/lantern/image_models.py — verify_image_models.py checks the
// seam, and checks both against NanoGPT's live price list.
//
// Estimates are exact, not flat: slide 1 paints unanchored, slides 2+ carry
// the style ref (the queue guarantees that order), so painters whose edit
// twin costs differently (FLUX Klein) price the two honestly.

import { DEFAULT_IMAGE_MODEL, IMAGE_MODELS_BY_ID } from '../config/imageModels'
import type { SlideSize } from './types'

function spec(imageModelId: string) {
  return IMAGE_MODELS_BY_ID[imageModelId] ?? IMAGE_MODELS_BY_ID[DEFAULT_IMAGE_MODEL]
}

export function estimateSlideCost(
  imageModelId: string,
  size: SlideSize,
  hasRef: boolean,
): number {
  const m = spec(imageModelId)
  if (hasRef && !m.imageToImage && m.edit) return m.edit.priceUsd
  return m.priceUsd[size]
}

export function estimateDeckCost(
  slideCount: number,
  size: SlideSize,
  imageModelId: string,
): number {
  if (slideCount <= 0) return 0
  let total = estimateSlideCost(imageModelId, size, false)
  if (slideCount > 1) total += (slideCount - 1) * estimateSlideCost(imageModelId, size, true)
  return total
}

export function formatUsd(n: number): string {
  return `$${n.toFixed(2)}`
}
