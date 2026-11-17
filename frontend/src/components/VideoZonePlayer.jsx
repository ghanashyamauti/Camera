import React, { useState, useRef, useEffect } from 'react'
import { Square, RotateCcw, Camera, ShieldCheck, ShieldAlert, Sparkles, Check } from 'lucide-react'

export default function VideoZonePlayer({
  streamUrl,
  status,
  zones,
  onSaveZones,
  onManualSnapshot,
  isSnapshotting
}) {
  const containerRef = useRef(null)
  const [isDrawing, setIsDrawing] = useState(false)
  const [drawStart, setDrawStart] = useState(null)
  const [currentBox, setCurrentBox] = useState(null)
  const [isDrawMode, setIsDrawMode] = useState(false)
  const [notification, setNotification] = useState(null)

  // Get first active zone or default
  const activeZone = zones && zones.length > 0 ? zones[0] : null
  const zoneStatus = status?.zones?.find(z => z.id === activeZone?.id) || status?.zones?.[0]
  const isOccupied = zoneStatus?.occupied || false
  const detectedObjects = zoneStatus?.detected_objects || []

  // Flash notification helper
  const showNotice = (msg) => {
    setNotification(msg)
    setTimeout(() => setNotification(null), 3000)
  }

  // Handle drawing coordinates normalized to [0, 1]
  const handleMouseDown = (e) => {
    if (!isDrawMode || !containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    const y = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height))
    setIsDrawing(true)
    setDrawStart({ x, y })
    setCurrentBox({ x, y, width: 0, height: 0 })
  }

  const handleMouseMove = (e) => {
    if (!isDrawing || !drawStart || !containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const currentX = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    const currentY = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height))

    const x = Math.min(drawStart.x, currentX)
    const y = Math.min(drawStart.y, currentY)
    const width = Math.abs(currentX - drawStart.x)
    const height = Math.abs(currentY - drawStart.y)

    setCurrentBox({ x, y, width, height })
  }

  const handleMouseUp = () => {
    if (!isDrawing) return
    setIsDrawing(false)

    // Only save if drawn box is meaningful size (> 3% width and height)
    if (currentBox && currentBox.width > 0.03 && currentBox.height > 0.03) {
      const newZone = {
        id: activeZone ? activeZone.id : 'zone-main',
        name: 'Monitored Zone',
        x: Math.round(currentBox.x * 1000) / 1000,
        y: Math.round(currentBox.y * 1000) / 1000,
        width: Math.round(currentBox.width * 1000) / 1000,
        height: Math.round(currentBox.height * 1000) / 1000,
        active: true
      }
      onSaveZones([newZone])
      showNotice('Zone updated successfully!')
      setIsDrawMode(false)
    }
    setCurrentBox(null)
    setDrawStart(null)
  }

  // Preset zone selectors
  const applyPreset = (preset) => {
    let newZone = { id: 'zone-main', name: 'Monitored Zone', active: true }
    if (preset === 'center') {
      newZone = { ...newZone, x: 0.25, y: 0.20, width: 0.50, height: 0.60 }
    } else if (preset === 'left') {
      newZone = { ...newZone, x: 0.05, y: 0.10, width: 0.42, height: 0.80 }
    } else if (preset === 'right') {
      newZone = { ...newZone, x: 0.53, y: 0.10, width: 0.42, height: 0.80 }
    } else if (preset === 'full') {
      newZone = { ...newZone, x: 0.05, y: 0.05, width: 0.90, height: 0.90 }
    }
    onSaveZones([newZone])
    showNotice(`Applied ${preset} zone preset`)
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-200/90 shadow-xs p-5 transition-all">
      {/* Top Card Bar */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <span className="font-semibold text-slate-800 text-sm">Live Stream & Detection Area</span>
          {isOccupied ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200/80 animate-fade-in">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
              Occupied ({detectedObjects.map(o => o.label).join(', ') || 'Object in Zone'})
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-50 text-rose-600 border border-rose-200/80">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
              Zone Clear / Empty
            </span>
          )}
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsDrawMode(!isDrawMode)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              isDrawMode
                ? 'bg-emerald-600 text-white shadow-xs'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200/80'
            }`}
          >
            <Square className="w-3.5 h-3.5" />
            <span>{isDrawMode ? 'Drawing Active (Drag to Mark)' : 'Draw Zone Box'}</span>
          </button>

          <button
            onClick={() => applyPreset('center')}
            title="Reset to center box"
            className="p-1.5 rounded-lg text-slate-500 bg-slate-50 hover:bg-slate-100 border border-slate-200 text-xs transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={onManualSnapshot}
            disabled={isSnapshotting}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 transition-colors shadow-2xs"
          >
            <Camera className="w-3.5 h-3.5 text-slate-500" />
            <span>{isSnapshotting ? 'Saving...' : 'Snapshot'}</span>
          </button>
        </div>
      </div>

      {/* Video Container with Interactive Drawing Canvas */}
      <div
        ref={containerRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        className={`relative aspect-video w-full rounded-xl overflow-hidden bg-slate-900 border border-slate-200/80 select-none ${
          isDrawMode ? 'cursor-crosshair ring-2 ring-emerald-500/50' : 'cursor-default'
        }`}
      >
        {/* Stream image */}
        <img
          src={streamUrl}
          alt="Live Stream"
          className="w-full h-full object-contain"
          onError={(e) => {
            // Keep retrying quietly
            setTimeout(() => {
              if (e.target) e.target.src = `${streamUrl}?t=${Date.now()}`
            }, 2000)
          }}
        />

        {/* Current In-Progress Drawn Box */}
        {isDrawing && currentBox && (
          <div
            className="absolute border-2 border-emerald-400 bg-emerald-400/20 pointer-events-none rounded-md"
            style={{
              left: `${currentBox.x * 100}%`,
              top: `${currentBox.y * 100}%`,
              width: `${currentBox.width * 100}%`,
              height: `${currentBox.height * 100}%`,
            }}
          >
            <span className="absolute -top-6 left-0 px-2 py-0.5 rounded bg-emerald-600 text-[10px] font-semibold text-white uppercase tracking-wider">
              Drawing Area...
            </span>
          </div>
        )}

        {/* Draw Mode Helper Banner */}
        {isDrawMode && !isDrawing && (
          <div className="absolute top-3 left-1/2 -translate-x-1/2 px-3 py-1.5 rounded-lg bg-slate-900/85 backdrop-blur-sm text-white text-xs font-medium flex items-center gap-2 pointer-events-none shadow-md">
            <Square className="w-3.5 h-3.5 text-emerald-400" />
            <span>Click and drag on the video to square the area you want to monitor</span>
          </div>
        )}

        {/* Floating Live Occupancy Tag */}
        <div className="absolute bottom-3 left-3 pointer-events-none">
          <div
            className={`px-3 py-1.5 rounded-lg backdrop-blur-md text-xs font-semibold flex items-center gap-2 shadow-sm transition-all ${
              isOccupied
                ? 'bg-emerald-600/90 text-white'
                : 'bg-rose-600/90 text-white'
            }`}
          >
            {isOccupied ? (
              <>
                <ShieldCheck className="w-4 h-4 text-emerald-100" />
                <span>
                  {detectedObjects.length > 0
                    ? `Occupied: ${detectedObjects.map(o => `${o.label} (${Math.round(o.confidence * 100)}%)`).join(', ')}`
                    : 'Thing Detected in Marked Zone (Green)'}
                </span>
              </>
            ) : (
              <>
                <ShieldAlert className="w-4 h-4 text-rose-100" />
                <span>No Object in Marked Zone (Red)</span>
              </>
            )}
          </div>
        </div>

        {/* Notification Toast */}
        {notification && (
          <div className="absolute top-3 right-3 px-3 py-1.5 rounded-lg bg-white/95 text-slate-800 text-xs font-medium border border-slate-200/80 shadow-md flex items-center gap-1.5 animate-fade-in">
            <Check className="w-3.5 h-3.5 text-emerald-600" />
            <span>{notification}</span>
          </div>
        )}
      </div>

      {/* Preset Zone Quick Pill Bar */}
      <div className="mt-3.5 flex items-center justify-between text-xs text-slate-500">
        <div className="flex items-center gap-1.5">
          <span className="font-medium text-slate-600">Quick Zone Presets:</span>
          <button
            onClick={() => applyPreset('center')}
            className="px-2.5 py-1 rounded-md bg-slate-100 hover:bg-slate-200/80 text-slate-700 transition-colors font-medium text-[11px]"
          >
            Center Box
          </button>
          <button
            onClick={() => applyPreset('left')}
            className="px-2.5 py-1 rounded-md bg-slate-100 hover:bg-slate-200/80 text-slate-700 transition-colors font-medium text-[11px]"
          >
            Left Half
          </button>
          <button
            onClick={() => applyPreset('right')}
            className="px-2.5 py-1 rounded-md bg-slate-100 hover:bg-slate-200/80 text-slate-700 transition-colors font-medium text-[11px]"
          >
            Right Half
          </button>
          <button
            onClick={() => applyPreset('full')}
            className="px-2.5 py-1 rounded-md bg-slate-100 hover:bg-slate-200/80 text-slate-700 transition-colors font-medium text-[11px]"
          >
            Full View
          </button>
        </div>

        <span className="text-[11px] text-slate-400">
          Tip: Click "Draw Zone Box" to freely mark any chair, car, or spot
        </span>
      </div>
    </div>
  )
}
