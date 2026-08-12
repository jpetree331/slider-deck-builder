// Sprint 1 verify — chassis seams, headless. Run: node scripts/verify-sprint1.mjs
import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const repo = join(dirname(fileURLToPath(import.meta.url)), '..')
const fails = []
const check = (name, cond) => {
  console.log((cond ? '  ok  ' : '  FAIL') + '  ' + name)
  if (!cond) fails.push(name)
}
const read = (p) => readFileSync(join(repo, p), 'utf-8')

console.log('verify-sprint1: lib purity (Sacred Invariant 5)')
for (const f of readdirSync(join(repo, 'dashboard/src/lib'))) {
  const src = read(join('dashboard/src/lib', f))
  check(`lib/${f} has no React import`, !/from\s+['"]react/.test(src))
}

console.log('verify-sprint1: ports & proxy')
const vite = read('dashboard/vite.config.ts')
check('vite dev port is 5179', /port:\s*5179/.test(vite))
check('vite proxies /api to 8020', /['"]\/api['"]:\s*['"]http:\/\/localhost:8020['"]/.test(vite))

console.log('verify-sprint1: env surface')
const envExample = read('.env.example')
for (const knob of [
  'ANTHROPIC_API_KEY',
  'GEMINI_API_KEY',
  'LANTERN_PORT=8020',
  'LANTERN_DATA_DIR=data',
  'LANTERN_PASSWORD=',
  'LANTERN_OUTLINE_MODEL=claude-haiku-4-5-20251001',
  'LANTERN_IMAGE_MODEL=gemini-3-pro-image-preview',
  'LANTERN_MAX_SLIDES=16',
]) {
  check(`.env.example carries ${knob.split('=')[0]}`, envExample.includes(knob))
}

console.log('verify-sprint1: backend purity + canonical order')
const storePy = read('src/lantern/store.py')
check('store.py imports no FastAPI', !/^\s*(import|from)\s+fastapi/m.test(storePy))
const apiPy = read('src/lantern/api.py')
check(
  'StaticFiles mounted after api_router include',
  apiPy.indexOf('include_router') < apiPy.indexOf('app.mount('),
)
check('CORS locked to 5179 origin', apiPy.includes('VITE_DEV_ORIGIN'))
check('health probe present', apiPy.includes('"service": "lantern"'))

console.log('verify-sprint1: types mirror deck.json')
const types = read('dashboard/src/lib/types.ts')
for (const field of [
  'id', 'title', 'topic', 'source_notes', 'style_guide', 'slide_size',
  'aspect_ratio', 'status', 'slides', 'created_at', 'updated_at',
  'palette', 'typography', 'motif', 'art_direction', 'tone',
  'visual_description', 'layout_hint', 'cost_estimate_usd', 'rendered_at',
]) {
  check(`types.ts carries ${field}`, types.includes(field))
}

console.log('verify-sprint1: ops files')
check('start-lantern.cmd exists', existsSync(join(repo, 'start-lantern.cmd')))
check('RUNBOOK has ports table', read('RUNBOOK.md').includes('8020'))
check('data/ gitignored', read('.gitignore').includes('data/*'))

if (fails.length) {
  console.log(`\n${fails.length} FAILURES:\n  ` + fails.join('\n  '))
  process.exit(1)
}
console.log('\nall sprint-1 checks passed')
