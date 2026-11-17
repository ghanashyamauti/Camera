import React, { useState } from 'react'
import { X, Video, Sliders, RefreshCw, Search, CheckCircle2, AlertCircle, Wifi } from 'lucide-react'

export default function SettingsModal({
  isOpen,
  onClose,
  config,
  onSaveConfig,
  onScanNetwork,
  isScanning,
  scanResults
}) {
  const [source, setSource] = useState(config?.source || '')
  const [confidence, setConfidence] = useState(config?.confidence || 0.45)
  const [message, setMessage] = useState(null)

  if (!isOpen) return null

  const handleSave = async (e) => {
    e.preventDefault()
    await onSaveConfig({ source, confidence })
    setMessage('Settings applied successfully!')
    setTimeout(() => setMessage(null), 3000)
  }

  const setPreset = (presetSource) => {
    setSource(presetSource)
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/30 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200 overflow-hidden animate-scale-in">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200/80 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-slate-100 text-slate-800">
              <Video className="w-4 h-4" />
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
        <form onSubmit={handleSave} className="p-6 space-y-5">
          
          {/* Quick Presets */}
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-2">
              Select Camera Source Preset
            </label>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => setPreset('rtsp://admin:Admin@123@192.168.0.100:554/cam/realmonitor?channel=1&subtype=1')}
                className={`p-2.5 rounded-xl text-left border transition-all ${
                  source.includes('192.168.0.100') || source.startsWith('rtsp')
                    ? 'border-emerald-500 bg-emerald-50/50 text-slate-900 ring-1 ring-emerald-500'
                    : 'border-slate-200 hover:border-slate-300 bg-slate-50/50 text-slate-700'
                }`}
              >
                <span className="block text-xs font-semibold">CP PLUS RTSP</span>
                <span className="block text-[10px] text-slate-500 mt-0.5">192.168.0.100 (Admin@123)</span>
              </button>

              <button
                type="button"
                onClick={() => setPreset('0')}
                className={`p-2.5 rounded-xl text-left border transition-all ${
                  source === '0' || source === 'webcam'
                    ? 'border-emerald-500 bg-emerald-50/50 text-slate-900 ring-1 ring-emerald-500'
                    : 'border-slate-200 hover:border-slate-300 bg-slate-50/50 text-slate-700'
                }`}
              >
                <span className="block text-xs font-semibold">Webcam (0)</span>
                <span className="block text-[10px] text-slate-500 mt-0.5">Built-in / USB</span>
              </button>

              <button
                type="button"
                onClick={() => setPreset('demo')}
                className={`p-2.5 rounded-xl text-left border transition-all ${
                  source === 'demo'
                    ? 'border-emerald-500 bg-emerald-50/50 text-slate-900 ring-1 ring-emerald-500'
                    : 'border-slate-200 hover:border-slate-300 bg-slate-50/50 text-slate-700'
                }`}
              >
                <span className="block text-xs font-semibold">Demo Room</span>
                <span className="block text-[10px] text-slate-500 mt-0.5">Simulation</span>
              </button>
            </div>
          </div>

          {/* Stream URL input */}
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1.5">
              Stream Source / RTSP URL
            </label>
            <input
              type="text"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="rtsp://admin:password@IP:554/cam/realmonitor?channel=1&subtype=1"
              className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-800 font-mono text-slate-800"
            />
            <p className="text-[11px] text-slate-400 mt-1">
              For CP PLUS: <code className="text-slate-600 bg-slate-100 px-1 py-0.5 rounded">rtsp://admin:pass@IP:554/cam/realmonitor?channel=1&subtype=1</code>
            </p>
          </div>

          {/* Scanner Tool */}
          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Wifi className="w-4 h-4 text-slate-500" />
                <div>
                  <h4 className="text-xs font-semibold text-slate-800">Find Camera on Network</h4>
                  <p className="text-[11px] text-slate-500">Scan for IP cameras (CP PLUS default 192.168.1.250)</p>
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
                          onClick={() => setSource(`rtsp://admin:admin123@${d.ip}:554/cam/realmonitor?channel=1&subtype=1`)}
                          className="text-[11px] text-emerald-600 font-medium hover:underline"
                        >
                          Use this RTSP
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[11px] text-slate-400">
                    No camera found yet. Make sure your PC is connected to <span className="font-semibold text-slate-600">TP-Link_B2B7</span> Wi-Fi.
                  </p>
                )}
              </div>
            )}
          </div>

          {/* AI Confidence Threshold */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-slate-700">
                Detection Confidence Threshold
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
            <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
              <span>More Sensitive (20%)</span>
              <span>Balanced (45%)</span>
              <span>Strict (85%)</span>
            </div>
          </div>

          {/* Notification Message */}
          {message && (
            <div className="p-2.5 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-medium flex items-center gap-2 border border-emerald-200">
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
              type="submit"
              className="px-4 py-2 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 active:bg-black rounded-lg shadow-2xs transition-colors"
            >
              Save Settings
            </button>
          </div>

        </form>

      </div>
    </div>
  )
}
