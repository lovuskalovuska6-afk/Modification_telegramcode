import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'
const __dirname = path.dirname(fileURLToPath(import.meta.url))
const srcDir = path.join(__dirname, '..', 'src')
const parts = []
for (let i = 0; i < 6; i++) {
  const p = path.join(srcDir, `app_b64_${i}.txt`)
  if (!fs.existsSync(p)) {
    console.error('missing', p)
    process.exit(1)
  }
  parts.push(fs.readFileSync(p, 'utf8').trim())
}
const b64 = parts.join('')
const jsx = Buffer.from(b64, 'base64').toString('utf8')
fs.writeFileSync(path.join(srcDir, 'App.jsx'), jsx)
console.log('Assembled App.jsx', jsx.length, 'bytes')
