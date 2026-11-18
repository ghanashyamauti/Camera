import React, { useState, useRef } from 'react'
import {
  Square,
  Hexagon,
  Trash2,
  Camera,
  Check,
  Clock,
  Filter,
  Download
} from 'lucide-react'

const COMMON_CLASSES = [
  'person',
  'car',
  'motorcycle',
  'bicycle',
  'chair',
  'bottle',
  'cup',
  'laptop',
  'cell phone',
  'backpack',
  'handbag',
  'suitcase',
  'book',
  'tv'
]

function formatDuration(seconds) {
  if (!seconds || seconds < 0) return '0s'
  if (seconds < 60) return `${seconds}s`
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  if (mins < 60) return `${mins}m ${secs}s`
  const hrs = Math.floor(mins / 60)
  const remMins = mins % 60
  return `${hrs}h ${remMins}m`
}

function formatSince(ts) {
  if (!ts) return ''
  try {
    return new Date(ts * 1000).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch {
    return ''
  }
}

export default function VideoZonePlayer({
  camera,
  streamUrl,
  apiUrl,
  liveZones = [],
  zones = [],
  onSaveZones,
  onManualSnapshot,
  isSnapshotting
}) {
  const containerRef = useRef(null)

  const [drawMode, setDrawMode] = useState(null)
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState(null)
  const [draftRect, setDraftRect] = useState(null)
  const [polyPoints, setPolyPoints] = useState([])
  const [cursorPos, setCursorPos] = useState(null)
  const [editingZoneId, setEditingZoneId] = useState(null)
  const [notification, setNotification] = useState(null)

  const showNotice = (msg) => {
    setNotification(msg)
    setTimeout(() => setNotification(null), 2500)
  }

  const getRelativePoint = (e) => {
    if (!containerRef.current) return { x: 0, y: 0 }
    const rect = containerRef.current.getBoundingClientRect()
    const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    const y = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height))
    return { x: Math.round(x * 1000) / 1000, y: Math.round(y * 1000) / 1000 }
  }

  const startDrawMode = (mode) => {
    if (drawMode === mode) {
      setDrawMode(null)
      setIsDragging(false)
      setDraftRect(null)
      setPolyPoints([])
      return
    }
    setDrawMode(mode)
    setIsDragging(false)
    setDraftRect(null)
    setPolyPoints([])
  }

  const commitNewZone = (zoneObj) => {
    const updated = [...(zones || []), zoneObj]
    onSaveZones(updated)
    showNotice(`Added "${zoneObj.name}"`)
    setDrawMode(null)
    setDraftRect(null)
    setPolyPoints([])
  }

  const handleMouseDown = (e) => {
    if (!drawMode || !containerRef.current) return
    const pt = getRelativePoint(e)

    if (drawMode === 'rect') {
      setIsDragging(true)
      setDragStart(pt)
      setDraftRect({ x: pt.x, y: pt.y, width: 0, height: 0 })
    } else if (drawMode === 'polygon') {
      if (polyPoints.length >= 3) {
        const first = polyPoints[0]
        const dist = Math.hypot(pt.x - first[0], pt.y - first[1])
        if (dist < 0.035) {
          finishPolygon()
          return
        }
      }
      setPolyPoints((prev) => [...prev, [pt.x, pt.y]])
    }
  }

  const handleMouseMove = (e) => {
    if (!drawMode || !containerRef.current) return
    const pt = getRelativePoint(e)

    if (drawMode === 'rect' && isDragging && dragStart) {
      const x = Math.min(dragStart.x, pt.x)
      const y = Math.min(dragStart.y, pt.y)
      const width = Math.abs(pt.x - dragStart.x)
      const height = Math.abs(pt.y - dragStart.y)
      setDraftRect({ x, y, width, height })
    } else if (drawMode === 'polygon') {
      setCursorPos(pt)
    }
  }

  const handleMouseUp = () => {
    if (drawMode === 'rect' && isDragging && draftRect) {
      setIsDragging(false)
      if (draftRect.width >= 0.03 && draftRect.height >= 0.03) {
        const zoneNumber = (zones || []).length + 1
        commitNewZone({
          id: `zone-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
          name: `Zone ${zoneNumber}`,
          type: 'rectangle',
          x: draftRect.x,
          y: draftRect.y,
          width: draftRect.width,
          height: draftRect.height,
          allowed_classes: []
        })
      } else {
        setDraftRect(null)
        setDrawMode(null)
      }
    }
  }

  const finishPolygon = () => {
    if (polyPoints.length < 3) {
      showNotice('Need at least 3 points for a shape')
      return
    }
    const zoneNumber = (zones || []).length + 1
    commitNewZone({
      id: `zone-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
      name: `Zone ${zoneNumber}`,
      type: 'polygon',
      points: polyPoints,
      allowed_classes: []
    })
  }

  const handleDeleteZone = (id) => {
    const updated = (zones || []).filter((z) => z.id !== id)
    onSaveZones(updated)
    if (editingZoneId === id) setEditingZoneId(null)
    showNotice('Zone deleted')
  }

  const handleClearAllZones = () => {
    if (!window.confirm('Delete all marked zones for this camera?')) return
    onSaveZones([])
    setEditingZoneId(null)
    setDrawMode(null)
    setPolyPoints([])
    showNotice('All zones cleared')
  }

  const handleRenameZone = (id, newName) => {
    const updated = (zones || []).map((z) => (z.id === id ? { ...z, name: newName } : z))
    onSaveZones(updated)
  }

  const handleToggleClassFilter = (zoneId, clsName) => {
    const updated = (zones || []).map((z) => {
      if (z.id !== zoneId) return z
      const current = z.allowed_classes || []
      const exists = current.includes(clsName)
      const next = exists ? current.filter((c) => c !== clsName) : [...current, clsName]
      return { ...z, allowed_classes: next }
    })
    onSaveZones(updated)
  }

  const handleClearClassFilter = (zoneId) => {
    const updated = (zones || []).map((z) => (z.id === zoneId ? { ...z, allowed_classes: [] } : z))
    onSaveZones(updated)
  }

  const occupiedCount = (liveZones || []).filter((z) => z.occupied).length

  return (
    <div className="space-y-4">
      {/* Main Video & Toolbar Card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-3 sm:p-4">
        {/* Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-2.5 pb-3 border-b border-slate-100">
          <div className="flex flex-wrap items-center gap-1.5">
            {/* Draw Box Button */}
            <button
              onClick={() => startDrawMode('rect')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                drawMode === 'rect'
                  ? 'bg-emerald-600 text-white shadow-xs'
                  : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
              }`}
            >
              <Square className="w-3.5 h-3.5" />
              <span>{drawMode === 'rect' ? 'Cancel Box' : 'Draw Box'}</span>
            </button>

            {/* Draw Polygon Button */}
            <button
              onClick={() => startDrawMode('polygon')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                drawMode === 'polygon'
                  ? 'bg-emerald-600 text-white shadow-xs'
                  : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
              }`}
            >
              <Hexagon className="w-3.5 h-3.5" />
              <span>{drawMode === 'polygon' ? 'Cancel Polygon' : 'Draw Polygon'}</span>
            </button>

            {/* Finish Polygon Button */}
            {drawMode === 'polygon' && polyPoints.length >= 3 && (
              <button
                onClick={finishPolygon}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500 hover:bg-emerald-600 text-white shadow-xs animate-pulse"
              >
                <Check className="w-3.5 h-3.5" />
                <span>Finish Shape ({polyPoints.length} pts)</span>
              </button>
            )}

            {/* Clear All Zones */}
            {(zones || []).length > 0 && (
              <button
                onClick={handleClearAllZones}
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold text-rose-600 hover:bg-rose-50 transition-colors"
                title="Delete all zones for this camera"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Clear</span>
              </button>
            )}
          </div>

          {/* Right Action Buttons */}
          <div className="flex items-center gap-2">
            {/* CSV Export */}
            <a
              href={`${apiUrl}/api/events/export?camera_id=${encodeURIComponent(camera.id)}`}
              download
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-slate-200 transition-colors"
              title="Export event logs to CSV"
            >
              <Download className="w-3.5 h-3.5 text-slate-500" />
              <span className="hidden sm:inline">Export CSV</span>
            </a>

            {/* Snapshot Trigger */}
            <button
              onClick={onManualSnapshot}
              disabled={isSnapshotting}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-900 hover:bg-slate-800 text-white shadow-xs disabled:opacity-50"
            >
              <Camera className="w-3.5 h-3.5 text-emerald-400" />
              <span>{isSnapshotting ? 'Saving...' : 'Snapshot'}</span>
            </button>
          </div>
        </div>

        {/* Live Video Feed Container */}
        <div
          ref={containerRef}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          className={`relative aspect-video w-full mt-3 bg-slate-950 rounded-xl overflow-hidden select-none ${
            drawMode ? 'cursor-crosshair' : 'cursor-default'
          }`}
        >
          <img
            src={streamUrl}
            alt={camera?.name || 'Live Camera Stream'}
            draggable={false}
            className="w-full h-full object-fill select-none"
            onError={(e) => {
              setTimeout(() => {
                if (e.target) e.target.src = `${streamUrl}?t=${Date.now()}`
              }, 2500)
            }}
          />

          {/* SVG Overlay: Saved & Live Zones */}
          <svg
            className="absolute inset-0 w-full h-full pointer-events-none"
            viewBox="0 0 1000 1000"
            preserveAspectRatio="none"
          >
            {(zones || []).map((z) => {
              const live = (liveZones || []).find((lz) => lz.id === z.id)
              const occ = live?.occupied || false
              const color = occ ? '#10b981' : '#f43f5e'
              const fill = occ ? 'rgba(16, 185, 129, 0.28)' : 'rgba(244, 63, 94, 0.20)'

              if (z.type === 'polygon' && z.points && z.points.length >= 3) {
                const ptsStr = z.points.map((p) => `${p[0] * 1000},${p[1] * 1000}`).join(' ')
                const cx = (z.points.reduce((acc, p) => acc + p[0], 0) / z.points.length) * 1000
                const cy = (z.points.reduce((acc, p) => acc + p[1], 0) / z.points.length) * 1000

                return (
                  <g key={z.id}>
                    <polygon
                      points={ptsStr}
                      fill={fill}
                      stroke={color}
                      strokeWidth="3.5"
                      strokeDasharray={occ ? 'none' : '8 4'}
                    />
                    <text
                      x={cx}
                      y={cy}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      fill="#ffffff"
                      fontSize="22"
                      fontWeight="bold"
                      style={{ textShadow: '0 2px 4px rgba(0,0,0,0.85)' }}
                    >
                      {z.name} {occ ? '●' : '○'}
                    </text>
                  </g>
                )
              } else {
                const x = z.x * 1000
                const y = z.y * 1000
                const w = z.width * 1000
                const h = z.height * 1000

                return (
                  <g key={z.id}>
                    <rect
                      x={x}
                      y={y}
                      width={w}
                      height={h}
                      fill={fill}
                      stroke={color}
                      strokeWidth="3.5"
                      strokeDasharray={occ ? 'none' : '8 4'}
                      rx="8"
                    />
                    <text
                      x={x + w / 2}
                      y={y + h / 2}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      fill="#ffffff"
                      fontSize="22"
                      fontWeight="bold"
                      style={{ textShadow: '0 2px 4px rgba(0,0,0,0.85)' }}
                    >
                      {z.name} {occ ? '●' : '○'}
                    </text>
                  </g>
                )
              }
            })}

            {/* In-Progress Rectangle Draft */}
            {drawMode === 'rect' && draftRect && (
              <rect
                x={draftRect.x * 1000}
                y={draftRect.y * 1000}
                width={draftRect.width * 1000}
                height={draftRect.height * 1000}
                fill="rgba(52, 211, 153, 0.25)"
                stroke="#34d399"
                strokeWidth="3"
                strokeDasharray="8 4"
                rx="6"
              />
            )}

            {/* In-Progress Polygon Draft */}
            {drawMode === 'polygon' && polyPoints.length > 0 && (
              <>
                <polygon
                  points={[
                    ...polyPoints,
                    ...(cursorPos ? [[cursorPos.x, cursorPos.y]] : [])
                  ]
                    .map((p) => `${p[0] * 1000},${p[1] * 1000}`)
                    .join(' ')}
                  fill="rgba(52, 211, 153, 0.22)"
                  stroke="#34d399"
                  strokeWidth="3.5"
                  strokeDasharray="8 4"
                />
                {polyPoints.map((p, idx) => (
                  <circle
                    key={idx}
                    cx={p[0] * 1000}
                    cy={p[1] * 1000}
                    r={idx === 0 ? 10 : 6}
                    fill={idx === 0 ? '#10b981' : '#ffffff'}
                    stroke="#065f46"
                    strokeWidth="2.5"
                  />
                ))}
              </>
            )}
          </svg>

          {/* Drawing Guidance Banners */}
          {drawMode === 'rect' && !isDragging && (
            <div className="absolute top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-lg bg-slate-900/90 text-white text-xs font-medium flex items-center gap-1.5 pointer-events-none shadow-md">
              <Square className="w-3.5 h-3.5 text-emerald-400" />
              <span>Click and drag to draw a box</span>
            </div>
          )}

          {drawMode === 'polygon' && (
            <div className="absolute top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-lg bg-slate-900/90 text-white text-xs font-medium flex items-center gap-1.5 pointer-events-none shadow-md">
              <Hexagon className="w-3.5 h-3.5 text-emerald-400" />
              <span>
                {polyPoints.length < 3
                  ? `Click corners to trace polygon (${polyPoints.length} points)`
                  : 'Click the green start point or press "Finish Shape"'}
              </span>
            </div>
          )}

          {/* Toast Notification */}
          {notification && (
            <div className="absolute top-3 right-3 px-3 py-1.5 rounded-lg bg-white/95 text-slate-800 text-xs font-semibold border border-slate-200 shadow-md flex items-center gap-1.5">
              <Check className="w-3.5 h-3.5 text-emerald-600" />
              <span>{notification}</span>
            </div>
          )}
        </div>
      </div>

      {/* Monitored Zones Live Cards */}
      {(zones || []).length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-3.5">
          <div className="flex items-center justify-between mb-2.5">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600">
              Monitored Zones ({(zones || []).length})
            </h3>
            <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
              {occupiedCount}/{(zones || []).length} Occupied
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {(zones || []).map((z) => {
              const live = (liveZones || []).find((lz) => lz.id === z.id)
              const isOccupied = live?.occupied || false
              const duration = live?.duration_seconds || 0
              const sinceStr = formatSince(live?.since_timestamp)
              const objs = live?.detected_objects || []
              const allowed = z.allowed_classes || []
              const isEditing = editingZoneId === z.id

              return (
                <div
                  key={z.id}
                  className={`rounded-xl border p-3 transition-all ${
                    isOccupied
                      ? 'bg-emerald-50/60 border-emerald-300'
                      : 'bg-rose-50/50 border-rose-200'
                  }`}
                >
                  {/* Zone Header */}
                  <div className="flex items-start justify-between gap-1.5">
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <span
                        className={`w-2 h-2 rounded-full shrink-0 ${
                          isOccupied ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'
                        }`}
                      />
                      <input
                        type="text"
                        value={z.name}
                        onChange={(e) => handleRenameZone(z.id, e.target.value)}
                        className="font-bold text-xs text-slate-900 bg-transparent border-b border-transparent hover:border-slate-300 focus:border-slate-600 focus:outline-none truncate w-full"
                        title="Click to rename zone"
                      />
                    </div>

                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => setEditingZoneId(isEditing ? null : z.id)}
                        className={`p-1 rounded-md text-xs transition-colors ${
                          isEditing || allowed.length > 0
                            ? 'bg-slate-900 text-white'
                            : 'text-slate-500 hover:bg-white/80'
                        }`}
                        title="Filter specific objects for this zone"
                      >
                        <Filter className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleDeleteZone(z.id)}
                        className="p-1 rounded-md text-slate-400 hover:text-rose-600 hover:bg-white/80 transition-colors"
                        title="Delete this zone"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Status & Duration */}
                  <div className="mt-2 flex items-center justify-between text-xs">
                    <span
                      className={`font-bold text-[10px] px-2 py-0.5 rounded-md ${
                        isOccupied ? 'bg-emerald-600 text-white' : 'bg-rose-600 text-white'
                      }`}
                    >
                      {isOccupied ? 'OCCUPIED' : 'EMPTY'}
                    </span>

                    <div className="flex items-center gap-1 text-[11px] font-mono font-semibold text-slate-700">
                      <Clock className="w-3 h-3 text-slate-500" />
                      <span>{formatDuration(duration)}</span>
                      {sinceStr && (
                        <span className="text-[10px] font-normal text-slate-400">
                          ({sinceStr})
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Detected Objects */}
                  <div className="mt-2 flex flex-wrap items-center gap-1">
                    {objs.length > 0 ? (
                      objs.map((o, idx) => (
                        <span
                          key={idx}
                          className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-white border border-emerald-200 text-emerald-800"
                        >
                          {o.label} {Math.round(o.confidence * 100)}%
                        </span>
                      ))
                    ) : (
                      <span className="text-[10px] text-slate-500">
                        {allowed.length > 0
                          ? `Watching: ${allowed.join(', ')}`
                          : 'Watching: Any object'}
                      </span>
                    )}
                  </div>

                  {/* Expandable Class Filter Picker */}
                  {isEditing && (
                    <div className="mt-2.5 pt-2 border-t border-slate-200/80 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-600">
                          Detect Only:
                        </span>
                        {allowed.length > 0 && (
                          <button
                            onClick={() => handleClearClassFilter(z.id)}
                            className="text-[10px] text-rose-600 hover:underline font-medium"
                          >
                            Reset (Any)
                          </button>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {COMMON_CLASSES.map((cls) => {
                          const selected = allowed.includes(cls)
                          return (
                            <button
                              key={cls}
                              type="button"
                              onClick={() => handleToggleClassFilter(z.id, cls)}
                              className={`px-1.5 py-0.5 rounded text-[10px] font-medium border transition-colors ${
                                selected
                                  ? 'bg-slate-900 text-white border-slate-900'
                                  : 'bg-white text-slate-600 border-slate-200 hover:border-slate-400'
                              }`}
                            >
                              {cls}
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
