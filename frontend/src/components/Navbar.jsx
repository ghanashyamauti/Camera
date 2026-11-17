import React from 'react'
import { Camera, Settings, Image as ImageIcon, Video, Laptop } from 'lucide-react'

export default function Navbar({
  status,
  onOpenSettings,
  onOpenSnapshots,
  snapshotCount,
  onToggleSource
}) {
  const isConnected = status?.connected
  const fps = status?.fps || 0
  const source = status?.source || 'Loading...'

  const isWebcam = source === '0' || source === 'webcam'
  const displaySource = source.startsWith('rtsp') 
    ? 'CP PLUS Camera' 
    : source === 'demo' 
      ? 'Auto-Connecting...' 
      : isWebcam 
        ? 'Laptop Webcam' 
        : source

  return (
    <header className="sticky top-0 z-30 bg-white/80 backdrop-blur-md border-b border-slate-200/80 px-6 py-3.5 transition-all">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        
        {/* Brand / Logo */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-slate-900 text-white flex items-center justify-center shadow-sm">
            <Camera className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-semibold text-slate-900 text-base tracking-tight">Thing Detector</h1>
              <span className="text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                Vision AI
              </span>
            </div>
            <p className="text-xs text-slate-500">Live zone occupancy & presence monitoring</p>
          </div>
        </div>

        {/* Center: Live stream indicator */}
        <div className="hidden md:flex items-center gap-3 px-3.5 py-1.5 rounded-full bg-slate-50 border border-slate-200/80 text-xs">
          <div className="flex items-center gap-1.5 font-medium">
            <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
            <span className={isConnected ? 'text-slate-800' : 'text-rose-600'}>
              {isConnected ? 'Stream Active' : 'Auto-Searching...'}
            </span>
          </div>
          <span className="text-slate-300">|</span>
          <div className="flex items-center gap-1 text-slate-500">
            <span>Source:</span>
            <span className="font-medium text-slate-700">{displaySource}</span>
          </div>
          <span className="text-slate-300">|</span>
          <div className="flex items-center gap-1 text-slate-500 font-mono text-[11px]">
            <span>{fps} FPS</span>
          </div>
        </div>

        {/* Right Action buttons */}
        <div className="flex items-center gap-2.5">
          {/* Quick Webcam / CP PLUS Toggle */}
          <button
            onClick={onToggleSource}
            title={isWebcam ? "Switch back to CP PLUS Camera" : "Instant fallback to Laptop Webcam"}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg transition-all shadow-xs ${
              isWebcam
                ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200/80 border border-slate-200'
            }`}
          >
            {isWebcam ? <Video className="w-3.5 h-3.5" /> : <Laptop className="w-3.5 h-3.5 text-slate-600" />}
            <span>{isWebcam ? 'Using Webcam (Click for CP PLUS)' : 'Use Webcam'}</span>
          </button>

          <button
            onClick={onOpenSnapshots}
            className="flex items-center gap-2 px-3.5 py-2 text-xs font-medium rounded-lg text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 active:bg-slate-100 transition-colors shadow-xs"
          >
            <ImageIcon className="w-4 h-4 text-slate-500" />
            <span>Captures</span>
            {snapshotCount > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-slate-100 text-slate-700 text-[10px] font-semibold">
                {snapshotCount}
              </span>
            )}
          </button>

          <button
            onClick={onOpenSettings}
            className="flex items-center gap-2 px-3.5 py-2 text-xs font-medium rounded-lg text-white bg-slate-900 hover:bg-slate-800 active:bg-black transition-colors shadow-xs"
          >
            <Settings className="w-4 h-4 text-slate-300" />
            <span>Settings</span>
          </button>
        </div>

      </div>
    </header>
  )
}
