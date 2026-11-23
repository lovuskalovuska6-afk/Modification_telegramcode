import fs from 'fs'
import path from 'path'
import zlib from 'zlib'
import { fileURLToPath } from 'url'
const __dirname = path.dirname(fileURLToPath(import.meta.url))
const srcDir = path.join(__dirname, '..', 'src')
let b64 = ''
for (let i = 0; i < 13; i++) {
  const p = path.join(srcDir, `app_z${i}.txt`)
  if (!fs.existsSync(p)) {
    console.error('missing', p)
    process.exit(1)
  }
  b64 += fs.readFileSync(p, 'utf8').trim()
}
const jsx = zlib.inflateSync(Buffer.from(b64, 'base64')).toString('utf8')
fs.writeFileSync(path.join(srcDir, 'App.jsx'), jsx)
console.log('Assembled App.jsx', jsx.length, 'bytes')
