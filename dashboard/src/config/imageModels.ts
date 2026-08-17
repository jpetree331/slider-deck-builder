// THE image model list — the only place painters are defined (same rule as
// models.ts: components never branch on model id). The backend mirrors these
// rows in src/lantern/image_models.py::IMAGE_MODELS; verify_image_models.py
// checks the two stay in sync — ids, providers, i2i flags, and every price.
// To add a painter: add a row here AND there.
//
// `sizes` maps the deck's slide_size (1K/2K/4K) to the token that provider's
// API expects for a 16:9 image at that tier. `edit` names the paired
// image-input variant a text-only model auto-routes to when a style anchor
// exists (slides 2+); its price is what those slides actually cost.

import type { SlideSize } from '../lib/types'

export interface ImageModelEdit {
  id: string
  size: string
  priceUsd: number
}

export interface ImageModel {
  id: string
  label: string
  provider: 'gemini' | 'nanogpt'
  imageToImage: boolean
  sizes: Record<SlideSize, string>
  priceUsd: Record<SlideSize, number>
  edit: ImageModelEdit | null
  note: string
}

export const DEFAULT_IMAGE_MODEL = 'gemini-3-pro-image-preview'

export const IMAGE_MODELS: ImageModel[] = [
  {
    id: 'gemini-3-pro-image-preview',
    label: 'Nano Banana Pro — Google',
    provider: 'gemini',
    imageToImage: true,
    sizes: { '1K': '1K', '2K': '2K', '4K': '4K' },
    priceUsd: { '1K': 0.134, '2K': 0.134, '4K': 0.24 },
    edit: null,
    note: 'default — your Google key, ~$0.13 a slide ($0.24 at 4K)',
  },
  {
    id: 'seedream-v4.5',
    label: 'Seedream 4.5 — NanoGPT',
    provider: 'nanogpt',
    imageToImage: true,
    sizes: { '1K': '4096x2304', '2K': '4096x2304', '4K': '4096x2304' },
    priceUsd: { '1K': 0.04, '2K': 0.04, '4K': 0.04 },
    edit: null,
    note: '4¢ a slide, 4K-sharp 16:9 at every size — the bargain',
  },
  {
    id: 'bytedance/seedream-v5.0-pro',
    label: 'Seedream 5.0 Pro — NanoGPT',
    provider: 'nanogpt',
    imageToImage: true,
    sizes: { '1K': '16:9', '2K': '16:9', '4K': '16:9' },
    priceUsd: { '1K': 0.09, '2K': 0.09, '4K': 0.09 },
    edit: null,
    note: '9¢ a slide — the newest Seedream, native 16:9',
  },
  {
    id: 'qwen-image-3-pro',
    label: 'Qwen Image 3 Pro — NanoGPT',
    provider: 'nanogpt',
    imageToImage: true,
    sizes: { '1K': '1k', '2K': '2k', '4K': '2k' },
    priceUsd: { '1K': 0.04, '2K': 0.075, '4K': 0.075 },
    edit: null,
    note: '4–7.5¢ a slide, strong painted text — 16:9 pending its first live paint',
  },
  {
    id: 'nano-banana-pro',
    label: 'Nano Banana Pro — NanoGPT',
    provider: 'nanogpt',
    imageToImage: true,
    sizes: { '1K': '1k', '2K': '2k', '4K': '4k' },
    priceUsd: { '1K': 0.14, '2K': 0.14, '4K': 0.24 },
    edit: null,
    note: 'the same painter, billed to your NanoGPT balance — 16:9 pending its first live paint',
  },
  {
    id: 'flux-2-klein-4b',
    label: 'FLUX.2 Klein 4B — NanoGPT',
    provider: 'nanogpt',
    imageToImage: false,
    sizes: { '1K': '1280*720', '2K': '1280*720', '4K': '1280*720' },
    priceUsd: { '1K': 0.0102, '2K': 0.0102, '4K': 0.0102 },
    edit: { id: 'wavespeed-ai/flux-2-klein-base-4b/edit', size: 'auto', priceUsd: 0.015 },
    note: '~1¢ a slide at 720p; anchored slides ride the Klein Edit twin (1.5¢)',
  },
  {
    id: 'flux-2-pro',
    label: 'FLUX.2 Pro — NanoGPT',
    provider: 'nanogpt',
    imageToImage: false,
    sizes: { '1K': '1280*720', '2K': '1280*720', '4K': '1280*720' },
    priceUsd: { '1K': 0.051, '2K': 0.051, '4K': 0.051 },
    edit: { id: 'flux-2-pro-image-to-image', size: 'auto', priceUsd: 0.051 },
    note: '5¢ a slide at 720p; anchored slides use its Edit twin, same price',
  },
]

export const IMAGE_MODELS_BY_ID: Record<string, ImageModel> = Object.fromEntries(
  IMAGE_MODELS.map((m) => [m.id, m]),
)
