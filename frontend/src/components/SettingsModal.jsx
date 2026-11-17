import React, { useState, useEffect } from 'react'
import { X, Video, Sliders, RefreshCw, Search, CheckCircle2, AlertCircle, Wifi, Key, Server } from 'lucide-react'

export default function SettingsModal({
  isOpen,
  onClose,
  config,
  onSaveConfig,
  onScanNetwork,
  isScanning,
  scanResults
}) {
  const [source, setSource] = useState(config?.source || 'rtsp://admin:Admin123!@192.168.0.100:554/cam/realmonitor?channel=1&subtype=1')
  const [confidence, setConfidence] = useState(config?.confidence || 0.45)
  const [cameraIp, setCameraIp] = useState(config?.camera_ip || '192.168.0.100')
  const [cameraUser, setCameraUser] = useState(config?.camera_user || 'admin')
  const [cameraPass, setCameraPass] = useState(config?.camera_password || 'Admin123!')
  const [message, setMessage] = useState(null)

  useEffect(() => {
    if (config) {
      if (config.camera_password) setCameraPass(config.camera_password)
      if (config.camera_ip) setCameraIp(config.camera_ip)
      if (config.camera_user) setCameraUser(config.camera_user)
      if (config.source) setSource(config.source)
    }
  }, [config])

  if (!isOpen) return null

  const handleSave = async (e) => {
    if (e) e.preventDefault()
    await onSaveConfig({ source, confidence })
    setMessage('Settings applied successfully! Connecting...')
    setTimeout(() => {
      setMessage(null)
      onClose()
    }, 1200)
  }

  const applyCredentials = (ip = cameraIp, user = cameraUser, pass = cameraPass) => {
    const url = `rtsp://${user}:${pass}@${ip}:554/cam/realmonitor?channel=1&subtype=1`
    setSource(url)
    return url
  }

  const handleQuickConnect = async () => {
    const url = applyCredentials()
    await onSaveConfig({ source: url, confidence })
    setMessage(`Connecting to Camera (${cameraPass})...`)
    setTimeout(() => {
      setMessage(null)
      onClose()
    }, 1200)
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/30 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200 overflow-hidden animate-scale-in">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200/80 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-slate-900 text-white">
              <Video className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Camera & Network Settings</h2>
              <p className="text-[11px] text-slate-500">Configure your CP PLUS camera or test video feed</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Form */}
        <div className="p-6 space-y-5">
          
          {/* CP PLUS Direct Credentials Card */}
          <div className="p-4 rounded-xl bg-emerald-50/60 border border-emerald-200/90 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Server className="w-4 h-4 text-emerald-700" />
                <span className="text-xs font-bold text-emerald-950 uppercase tracking-wider">
                  CP PLUS Camera Connection
                </span>
              </div>
              <span className="text-[10px] font-semibold bg-emerald-200/70 text-emerald-900 px-2 py-0.5 rounded-full">
                192.168.0.100
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="block text-[10px] font-medium text-slate-600 mb-1">Camera IP</label>
                <input
                  type="text"
                  value={cameraIp}
                  onChange={(e) => {
                    setCameraIp(e.target.value)
                    applyCredentials(e.target.value, cameraUser, cameraPass)
                  }}
                  className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-200 bg-white font-mono text-slate-800"
                />
              </div>

              <div>
                <label className="block text-[10px] font-medium text-slate-600 mb-1">Username</label>
                <input
                  type="text"
                  value={cameraUser}
                  onChange={(e) => {
                    setCameraUser(e.target.value)
                    applyCredentials(cameraIp, e.target.value, cameraPass)
                  }}
                  className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-200 bg-white font-mono text-slate-800"
                />
              </div>

              <div>
                <label className="block text-[10px] font-medium text-slate-600 mb-1">Password</label>
                <input
                  type="text"
                  value={cameraPass}
                  onChange={(e) => {
                    setCameraPass(e.target.value)
                    applyCredentials(cameraIp, cameraUser, e.target.value)
                  }}
                  className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-200 bg-white font-mono text-slate-800 font-semibold text-emerald-700"
                />
              </div>
            </div>

            <button
              type="button"
              onClick={handleQuickConnect}
              className="w-full py-2 px-3 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs transition-colors flex items-center justify-center gap-1.5"
            >
              <Video className="w-3.5 h-3.5" />
              <span>Connect to Camera ({cameraPass})</span>
            </button>
          </div>

          {/* Quick Presets */}
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-2">
              Other Video Sources
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => {
                  setSource('0')
                  onSaveConfig({ source: '0', confidence })
                  setMessage('Switched to Webcam (0)')
                  setTimeout(() => { setMessage(null); onClose() }, 1000)
                }}
                className={`p-2.5 rounded-xl text-left border transition-all ${
                  source === '0' || source === 'webcam'
                    ? 'border-emerald-500 bg-emerald-50/50 text-slate-900 ring-1 ring-emerald-500'
                    : 'border-slate-200 hover:border-slate-300 bg-slate-50/50 text-slate-700'
                }`}
              >
                <span className="block text-xs font-semibold">Webcam (0)</span>
                <span className="block text-[10px] text-slate-500 mt-0.5">Built-in / USB Camera</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setSource('demo')
                  onSaveConfig({ source: 'demo', confidence })
                  setMessage('Switched to Demo Simulation')
                  setTimeout(() => { setMessage(null); onClose() }, 1000)
                }}
                className={`p-2.5 rounded-xl text-left border transition-all ${
                  source === 'demo'
                    ? 'border-emerald-500 bg-emerald-50/50 text-slate-900 ring-1 ring-emerald-500'
                    : 'border-slate-200 hover:border-slate-300 bg-slate-50/50 text-slate-700'
                }`}
              >
                <span className="block text-xs font-semibold">Demo Room</span>
                <span className="block text-[10px] text-slate-500 mt-0.5">Simulated Video Feed</span>
              </button>
            </div>
          </div>

          {/* Stream URL input */}
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1.5">
              Active Stream RTSP URL
            </label>
            <input
              type="text"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="rtsp://admin:Admin@123@192.168.0.100:554/cam/realmonitor?channel=1&subtype=1"
              className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-800 font-mono text-slate-800"
            />
          </div>

          {/* Scanner Tool */}
          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Wifi className="w-4 h-4 text-slate-500" />
                <div>
                  <h4 className="text-xs font-semibold text-slate-800">Scan Network for Camera</h4>
                  <p className="text-[11px] text-slate-500">Scan for IP cameras on router</p>
                </div>
              </div>
              <button
                type="button"
                onClick={onScanNetwork}
                disabled={isScanning}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white border border-slate-200 hover:bg-slate-100 text-slate-700 transition-colors shadow-2xs"
              >
                {isScanning ? (
                  <>
                    <RefreshCw className="w-3 h-3 animate-spin text-slate-500" />
                    <span>Scanning...</span>
                  </>
                ) : (
                  <>
                    <Search className="w-3 h-3 text-slate-500" />
                    <span>Scan</span>
                  </>
                )}
              </button>
            </div>

            {/* Scan results */}
            {scanResults && (
              <div className="mt-2.5 pt-2.5 border-t border-slate-200 text-xs">
                {scanResults.found_devices && scanResults.found_devices.length > 0 ? (
                  <div className="space-y-1.5">
                    <span className="text-[11px] font-medium text-emerald-700">Found Devices:</span>
                    {scanResults.found_devices.map((d, i) => (
                      <div key={i} className="flex items-center justify-between bg-white px-2.5 py-1.5 rounded border border-slate-200">
                        <span className="font-mono text-[11px]">{d.ip}:{d.port}</span>
                        <button
                          type="button"
                          onClick={() => {
                            setCameraIp(d.ip)
                            const url = applyCredentials(d.ip, cameraUser, cameraPass)
                            onSaveConfig({ source: url, confidence })
                            setMessage(`Connected to ${d.ip}!`)
                            setTimeout(() => { setMessage(null); onClose() }, 1000)
                          }}
                          className="text-[11px] text-emerald-600 font-semibold hover:underline"
                        >
                          Use this RTSP ({cameraPass})
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[11px] text-slate-400">
                    No camera found yet. Make sure your PC is connected to <span className="font-semibold text-slate-600">Shakham_5G</span>.
                  </p>
                )}
              </div>
            )}
          </div>

          {/* AI Confidence Threshold */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-slate-700">
                Detection Sensitivity
              </label>
              <span className="text-xs font-mono font-semibold text-slate-800">
                {Math.round(confidence * 100)}%
              </span>
            </div>
            <input
              type="range"
              min="0.20"
              max="0.85"
              step="0.05"
              value={confidence}
              onChange={(e) => setConfidence(parseFloat(e.target.value))}
              className="w-full accent-slate-900 cursor-pointer"
            />
          </div>

          {/* Notification Message */}
          {message && (
            <div className="p-2.5 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-medium flex items-center gap-2 border border-emerald-200 animate-fade-in">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{message}</span>
            </div>
          )}

          {/* Footer Save Button */}
          <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-slate-600 hover:text-slate-800 rounded-lg"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSave}
              className="px-4 py-2 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 active:bg-black rounded-lg shadow-2xs transition-colors"
            >
              Save Settings
            </button>
          </div>

        </div>

      </div>
    </div>
  )
}
