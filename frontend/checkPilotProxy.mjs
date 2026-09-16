import assert from 'node:assert/strict'
import { loadConfigFromFile } from 'vite'

process.env.PILOT_API_TARGET = 'http://127.0.0.1:8001'
const loaded = await loadConfigFromFile({ command: 'serve', mode: 'development' })
assert.ok(loaded)
assert.equal(loaded.config.server.proxy['/api'].target, 'http://127.0.0.1:8001')
assert.equal(loaded.config.server.proxy['/ws'].target, 'ws://127.0.0.1:8001')

delete process.env.PILOT_API_TARGET
const standard = await loadConfigFromFile({ command: 'serve', mode: 'development' })
assert.ok(standard)
assert.equal(standard.config.server.proxy['/api'].target, 'http://localhost:8000')
assert.equal(standard.config.server.proxy['/ws'].target, 'ws://localhost:8000')
