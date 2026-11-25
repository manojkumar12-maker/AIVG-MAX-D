export const ASPECT_RATIOS = ['1:1', '16:9', '9:16', '4:3', '3:4', 'custom']

export const ASPECT_DIMENSIONS = {
  '1:1': { width: 1024, height: 1024 },
  '16:9': { width: 1280, height: 720 },
  '9:16': { width: 720, height: 1280 },
  '4:3': { width: 1024, height: 768 },
  '3:4': { width: 768, height: 1024 },
}

export const QUALITY_PRESETS = [
  {
    id: 'fast',
    label: 'Fast',
    description: 'Fewer steps, lower resolution — quickest results.',
    steps: 20,
    cfg: 6.0,
    resolutionScale: 0.75,
  },
  {
    id: 'balanced',
    label: 'Balanced',
    description: 'Default trade-off between speed and detail.',
    steps: 30,
    cfg: 7.0,
    resolutionScale: 1,
  },
  {
    id: 'quality',
    label: 'Quality',
    description: 'More steps at full resolution — slowest, most detail.',
    steps: 50,
    cfg: 7.5,
    resolutionScale: 1,
  },
]

export const SHORTS_PRESETS = [
  {
    id: 'shorts-portrait-image',
    label: 'Shorts Portrait Image',
    description: '576×1024 portrait frame for Shorts / TikTok / Reels thumbnails.',
    kind: 'image',
    width: 576,
    height: 1024,
    aspect: '9:16',
  },
  {
    id: 'shorts-video-576',
    label: 'Shorts Video 576p',
    description: '9:16 video at 576×1024 — lighter on GPU memory.',
    kind: 'video',
    width: 576,
    height: 1024,
    aspect: '9:16',
  },
  {
    id: 'shorts-video-720',
    label: 'Shorts Video 720p',
    description: '9:16 video at 720×1280 — sharper, needs more VRAM.',
    kind: 'video',
    width: 720,
    height: 1280,
    aspect: '9:16',
  },
]

export const CAMERA_MOVEMENTS = [
  'Static',
  'Zoom in',
  'Zoom out',
  'Pan left',
  'Pan right',
  'Tilt',
  'Dolly',
  'Cinematic',
]

export const DURATION_PRESETS = [
  { seconds: 2, fps: 16 },
  { seconds: 4, fps: 16 },
  { seconds: 8, fps: 24 },
]

export function framesForDuration(seconds, fps) {
  return Math.round(seconds * fps)
}

export function snapTo8(n, max) {
  const num = Math.max(64, Math.round(Number(n) || 64))
  const snapped = num - (num % 8)
  if (Number.isFinite(max)) return Math.min(snapped, Math.floor(max / 8) * 8)
  return snapped
}
