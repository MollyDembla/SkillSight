import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const root = resolve(frontend, '..')
const venvPython = resolve(root, '.venv', 'Scripts', 'python.exe')
const python = process.env.PYTHON || (existsSync(venvPython) ? venvPython : 'python')
const processes = [
  spawn(python, ['-m', 'uvicorn', 'backend.app:app'], { cwd: root, stdio: 'inherit', env: process.env }),
  spawn(process.execPath, [resolve(frontend, 'node_modules', 'vite', 'bin', 'vite.js'), '--host', '127.0.0.1'], { cwd: frontend, stdio: 'inherit', env: process.env }),
]
let stopping = false
function stop(code = 0) {
  if (stopping) return
  stopping = true
  for (const child of processes) if (!child.killed) child.kill('SIGTERM')
  setTimeout(() => process.exit(code), 250)
}
for (const child of processes) child.on('error', (error) => { console.error(error); stop(1) })
process.on('SIGINT', () => stop(0))
process.on('SIGTERM', () => stop(0))
processes.forEach((child) => child.on('exit', (code) => { if (!stopping && code !== 0) stop(code || 1) }))
