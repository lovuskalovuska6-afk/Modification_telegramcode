/**
 * Prebuild helper.
 * If a full App.jsx is already in src/ (committed directly), keep it.
 * Only assemble from app_z*.txt chunks when App.jsx is missing/tiny
 * (legacy path for when GitHub truncated large files).
 */
import fs from 'fs'
import path from 'path'
import zlib from 'zlib'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const srcDir = path.join(__dirname, '..', 'src')
const appPath = path.join(srcDir, 'App.jsx')

const MIN_FULL_SIZE = 15000

if (fs.existsSync(appPath)) {
  const size = fs.statSync(appPath).size
  if (size >= MIN_FULL_SIZE) {
    console.log('Using existing App.jsx', size, 'bytes (skip chunk assemble)')
    process.exit(0)
  }
  console.log('App.jsx too small (', size, '), trying assemble from chunks…')
}

let b64 = ''
const parts = []
for (let i = 0; i < 20; i++) {
  const p = path.join(srcDir, `app_z${i}.txt`)
  if (!fs.existsSync(p)) break
  parts.push(p)
  b64 += fs.readFileSync(p, 'utf8').trim()
}

if (!b64) {
  if (fs.existsSync(appPath) && fs.statSync(appPath).size > 0) {
    console.log('No chunks; keeping existing App.jsx')
    process.exit(0)
  }
  console.error('No App.jsx and no app_z*.txt chunks')
  process.exit(1)
}

try {
  const jsx = zlib.inflateSync(Buffer.from(b64, 'base64')).toString('utf8')
  fs.writeFileSync(appPath, jsx)
  console.log('Assembled App.jsx', jsx.length, 'bytes from', parts.length, 'chunks')
} catch (e) {
  if (fs.existsSync(appPath) && fs.statSync(appPath).size >= MIN_FULL_SIZE) {
    console.warn('Chunk assemble failed, keeping existing App.jsx:', e.message)
    process.exit(0)
  }
  console.error('Assemble failed and no valid App.jsx:', e.message)
  process.exit(1)
}
