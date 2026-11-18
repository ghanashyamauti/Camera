import React, { useState, useEffect } from 'react'
import { X, Video, Server, CheckCircle2, AlertCircle, Plus, Trash2, Search, RefreshCw, Sparkles, Eye, EyeOff } from 'lucide-react'

export default function SettingsModal({
  isOpen,
  onClose,
  apiUrl,
  cameras,
  initialTab = 'list',
  onAddCamera,
  onUpdateCamera,
  onDeleteCamera,
  onScanNetwork,
  isScanning,
  scanResults
}) {
  const [tab, setTab] = useState(initialTab) // 'list' | 'add'
  const [editingId, setEditingId] = useState(null)

  const [name, setName] = useState('')
  const [ip, setIp] = useState('')
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [subtype, setSubtype] = useState('1')

  const [isProbing, setIsProbing] = useState(false)
  const [probeResult, setProbeResult] = useState(null)
  const [isSaving, setIsSaving] = useState(false)
  const [message, setMessage] = useState(null)

  // Only reset form when modal transitions from closed -> open (NOT on background camera polling!)
  useEffect(() => {
    if (isOpen) {
      setTab(initialTab)
      setEditingId(null)
      setProbeResult(null)
      setMessage(null)
      setShowPassword(false)
      if (initialTab === 'add') {
        const nextNum = (cameras?.length || 0) + 1
        setName(`Camera ${nextNum}`)
        setIp('')
        setUsername('admin')
        setPassword('')
        setSubtype('1')
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, initialTab])

  if (!isOpen) return null

  const startEdit = (cam) => {
    setEditingId(cam.id)
    setName(cam.name)
    setIp(cam.ip)
    setUsername(cam.username || 'admin')
    setPassword('') // Blank = keep existing encrypted password in DB
    setSubtype(String(cam.subtype || '1'))
    setProbeResult(null)
    setMessage(null)
    setTab('add')
  }

  const startAddNew = (prefillIp = '') => {
    const nextNum = (cameras?.length || 0) + 1
    setEditingId(null)
    setName(`Camera ${nextNum}`)
    setIp(prefillIp)
    setUsername('admin')
    setPassword('')
    setSubtype('1')
    setProbeResult(null)
    setMessage(null)
    setTab('add')
  }

  const handleTestAutoDetect = async () => {
    if (!ip.trim() || !password) return
    setIsProbing(true)
    setProbeResult(null)
    try {
      const res = await fetch(`${apiUrl}/api/cameras/probe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ip: ip.trim(),
          username: username.trim() || 'admin',
          password,
          subtype
        })
      })
      if (res.ok) {
        const data = await res.json()
        setProbeResult(data)
      }
    } catch (err) {
      setProbeResult({ success: false, message: 'Probe request failed' })
    } finally {
      setIsProbing(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setIsSaving(true)
    setMessage(null)

    try {
      if (editingId) {
        const payload = {
          name: name.trim() || 'IP Camera',
          ip: ip.trim(),
          username: username.trim() || 'admin',
          subtype
        }
        if (password) payload.password = password
        await onUpdateCamera(editingId, payload)
        setMessage(`Updated ${payload.name}!`)
      } else {
        const payload = {
          name: name.trim() || 'IP Camera',
          ip: ip.trim(),
          username: username.trim() || 'admin',
          password,
          subtype,
          auto_detect: !probeResult?.success,
          port: probeResult?.success ? probeResult.port : null,
          protocol: probeResult?.success ? probeResult.protocol : null,
          stream_path: probeResult?.success ? probeResult.stream_path : null
        }
        await onAddCamera(payload)
        setMessage(`Added & connected ${payload.name}!`)
      }

      setTimeout(() => {
        setMessage(null)
        setEditingId(null)
        setProbeResult(null)
        setTab('list')
      }, 900)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200 overflow-hidden">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/60">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-emerald-600 text-white shadow-xs">
              <Video className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Camera Management</h2>
              <p className="text-[11px] text-slate-500">Auto-detects port, protocol & stream path • Stored in PostgreSQL</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tabs */}
        <div className="px-6 pt-4 flex items-center gap-2 border-b border-slate-100 pb-3">
          <button
            onClick={() => { setTab('list'); setEditingId(null) }}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              tab === 'list' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            Cameras ({cameras?.length || 0})
          </button>
          <button
            onClick={() => startAddNew()}
            className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              tab === 'add' ? 'bg-emerald-600 text-white' : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
            }`}
          >
            <Plus className="w-3.5 h-3.5" />
            <span>{editingId ? 'Edit Camera' : 'Add New Camera'}</span>
          </button>
        </div>

        <div className="p-6">
          {tab === 'list' ? (
            <div className="space-y-3">
              {(cameras || []).length === 0 ? (
                <div className="p-6 rounded-xl border border-dashed border-slate-300 text-center space-y-2">
                  <p className="text-xs font-semibold text-slate-700">No cameras added yet</p>
                  <p className="text-[11px] text-slate-500">
                    Click "Add New Camera" or scan your router below to discover cameras automatically.
                  </p>
                </div>
              ) : (
                (cameras || []).map((cam) => (
                  <div
                    key={cam.id}
                    className="p-3.5 rounded-xl border border-slate-200 bg-slate-50/70 flex items-center justify-between gap-3"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full shrink-0 ${cam.connected ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                        <span className="text-xs font-bold text-slate-900 truncate">{cam.name}</span>
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white border border-slate-200 text-slate-600">
                          {cam.ip}:{cam.port} ({(cam.protocol || 'rtsps').toUpperCase()})
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-500 mt-1 truncate">
                        {cam.connected ? `Live • ${cam.fps} FPS` : cam.status_message}
                        {cam.model ? ` • ${cam.model}` : ''}
                      </p>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      <button
                        onClick={() => startEdit(cam)}
                        className="px-2.5 py-1 rounded-lg text-xs font-medium bg-white border border-slate-200 hover:bg-slate-100 text-slate-700"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => onDeleteCamera(cam.id)}
                        className="p-1.5 rounded-lg text-rose-600 bg-rose-50 hover:bg-rose-100 border border-rose-200"
                        title="Remove camera"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))
              )}

              {/* Network Auto-Discovery */}
              <div className="pt-3 border-t border-slate-100">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold text-slate-800">Auto-Discover Cameras on Network</p>
                    <p className="text-[11px] text-slate-500">ONVIF multicast + RTSP port scan across local subnets</p>
                  </div>
                  <button
                    type="button"
                    onClick={onScanNetwork}
                    disabled={isScanning}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white border border-slate-200 hover:bg-slate-100 text-slate-700"
                  >
                    {isScanning ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                    <span>{isScanning ? 'Scanning...' : 'Scan LAN'}</span>
                  </button>
                </div>

                {scanResults && (
                  <div className="mt-2.5 space-y-1.5">
                    {scanResults.found_devices && scanResults.found_devices.length > 0 ? (
                      scanResults.found_devices.map((d, i) => {
                        const alreadyAdded = (cameras || []).some(c => c.ip === d.ip)
                        return (
                          <div key={i} className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-xs">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-slate-800">{d.ip}:{d.port}</span>
                              <span className="text-[10px] text-slate-400">{d.method}</span>
                            </div>
                            {alreadyAdded ? (
                              <span className="text-[11px] text-slate-400 font-medium">Added</span>
                            ) : (
                              <button
                                onClick={() => startAddNew(d.ip)}
                                className="text-[11px] font-semibold text-emerald-600 hover:underline"
                              >
                                + Add Camera
                              </button>
                            )}
                          </div>
                        )
                      })
                    ) : (
                      <p className="text-[11px] text-slate-400">No cameras found on local network.</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Server className="w-4 h-4 text-emerald-600" />
                    <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                      {editingId ? 'Edit Camera Credentials' : 'Enter Camera Credentials'}
                    </span>
                  </div>
                  <span className="text-[10px] font-semibold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full">
                    Auto Port & Protocol
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2.5">
                  <div>
                    <label className="block text-[11px] font-medium text-slate-600 mb-1">Camera Name</label>
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Entrance / Desk Cam"
                      className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 bg-white text-slate-800"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-slate-600 mb-1">Camera IP Address</label>
                    <input
                      type="text"
                      value={ip}
                      onChange={(e) => { setIp(e.target.value); setProbeResult(null) }}
                      placeholder="192.168.0.101"
                      className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 bg-white font-mono text-slate-800"
                      required
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2.5">
                  <div>
                    <label className="block text-[11px] font-medium text-slate-600 mb-1">Username</label>
                    <input
                      type="text"
                      value={username}
                      onChange={(e) => { setUsername(e.target.value); setProbeResult(null) }}
                      placeholder="admin"
                      className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 bg-white font-mono text-slate-800"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-slate-600 mb-1">
                      Password {editingId ? '(blank = unchanged)' : ''}
                    </label>
                    <div className="relative">
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={password}
                        onChange={(e) => { setPassword(e.target.value); setProbeResult(null) }}
                        placeholder={editingId ? '••••••••' : 'Camera password'}
                        className="w-full pl-3 pr-8 py-1.5 text-xs rounded-lg border border-slate-300 bg-white font-mono text-slate-800"
                        required={!editingId}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(prev => !prev)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700"
                        title={showPassword ? 'Hide password' : 'Show password'}
                      >
                        {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] font-medium text-slate-600 mb-1">Stream Profile</label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => { setSubtype('1'); setProbeResult(null) }}
                      className={`py-1.5 px-3 rounded-lg text-xs font-medium border ${
                        subtype === '1'
                          ? 'border-emerald-600 bg-emerald-50 text-emerald-800 font-semibold'
                          : 'border-slate-200 bg-white text-slate-600'
                      }`}
                    >
                      Sub Stream (Smooth / Multi-Cam)
                    </button>
                    <button
                      type="button"
                      onClick={() => { setSubtype('0'); setProbeResult(null) }}
                      className={`py-1.5 px-3 rounded-lg text-xs font-medium border ${
                        subtype === '0'
                          ? 'border-emerald-600 bg-emerald-50 text-emerald-800 font-semibold'
                          : 'border-slate-200 bg-white text-slate-600'
                      }`}
                    >
                      Main Stream (Full HD)
                    </button>
                  </div>
                </div>

                {/* Test Auto-Detect Button */}
                {!editingId && (
                  <button
                    type="button"
                    onClick={handleTestAutoDetect}
                    disabled={isProbing || !ip.trim() || !password}
                    className="w-full py-1.5 px-3 rounded-lg text-xs font-semibold bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 disabled:opacity-50 flex items-center justify-center gap-1.5"
                  >
                    {isProbing ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin text-emerald-600" />
                        <span>Auto-detecting port, ONVIF & protocol...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
                        <span>Test & Auto-Detect Stream</span>
                      </>
                    )}
                  </button>
                )}
              </div>

              {probeResult && (
                <div
                  className={`p-3 rounded-lg text-xs border flex items-start gap-2 ${
                    probeResult.success
                      ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                      : 'bg-amber-50 text-amber-800 border-amber-200'
                  }`}
                >
                  {probeResult.success ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  )}
                  <div>
                    <p className="font-semibold">{probeResult.message}</p>
                    {probeResult.model && (
                      <p className="text-[11px] opacity-80">
                        Device: {probeResult.manufacturer || ''} {probeResult.model} • Port {probeResult.port}
                      </p>
                    )}
                  </div>
                </div>
              )}

              {message && (
                <div className="p-2.5 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-medium flex items-center gap-2 border border-emerald-200">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>{message}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => { setTab('list'); setEditingId(null) }}
                  className="px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={isSaving}
                  className="px-5 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 rounded-lg shadow-sm"
                >
                  {isSaving ? 'Detecting & Saving...' : editingId ? 'Save Changes' : 'Add Camera'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
