import React from 'react'
import { Camera, Settings, Image as ImageIcon, Plus } from 'lucide-react'

export default function Navbar({
  cameras,
  onOpenSettings,
  onOpenAddCamera,
  onOpenSnapshots,
  snapshotCount
}) {
  const camList = cameras || []
  const connectedCount = camList.filter(c => c.connected).length
  const totalCount = camList.length

  return (
    <header className="sticky top-0 z-30 bg-white/90 backdrop-blur-md border-b border-slate-200 px-6 py-3">
      <div className="max-w-[1720px] mx-auto flex flex-wrap items-center justify-between gap-3">
        
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-slate-900 text-white flex items-center justify-center shadow-sm">
            <Camera className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h1 className="font-bold text-slate-900 text-base tracking-tight">Thing Detector</h1>
            <p className="text-[11px] text-slate-500">Multi-Camera CP PLUS Real-Time Monitor</p>
          </div>
        </div>

        {/* Center: Live Camera Status Badge */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-slate-50 border border-slate-200 text-xs">
            <span className={`w-2 h-2 rounded-full ${connectedCount > 0 ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
            <span className="font-semibold text-slate-700">
              {connectedCount}/{totalCount} Online
            </span>
          </div>
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={onOpenAddCamera}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg transition-colors shadow-2xs"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Camera</span>
          </button>

          <button
            onClick={onOpenSnapshots}
            className="relative flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg transition-colors shadow-2xs"
          >
            <ImageIcon className="w-3.5 h-3.5 text-slate-500" />
            <span>Snapshots</span>
            {snapshotCount > 0 && (
              <span className="ml-1 px-1.5 py-0.2 bg-emerald-100 text-emerald-700 rounded-full text-[10px] font-bold">
                {snapshotCount}
              </span>
            )}
          </button>

          <button
            onClick={onOpenSettings}
            className="flex items-center justify-center w-8 h-8 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-slate-200 transition-colors"
            title="Camera Settings & Auto-Detect"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>

      </div>
    </header>
  )
}
