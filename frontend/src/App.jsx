import React, { useState, useEffect, useCallback } from 'react'
import { Plus, Video, CheckCircle2 } from 'lucide-react'
import Navbar from './components/Navbar'
import VideoZonePlayer from './components/VideoZonePlayer'
import SnapshotsDrawer from './components/SnapshotsDrawer'
import SettingsModal from './components/SettingsModal'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function App() {
  const [cameras, setCameras] = useState([])
  const [selectedCameraId, setSelectedCameraId] = useState(null)
  const [snapshots, setSnapshots] = useState([])

  const [isSnapshotsOpen, setIsSnapshotsOpen] = useState(false)
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [settingsTab, setSettingsTab] = useState('list')
  const [snapshottingCameraId, setSnapshottingCameraId] = useState(null)
  const [isScanning, setIsScanning] = useState(false)
  const [scanResults, setScanResults] = useState(null)

  const fetchCameras = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/cameras`)
      if (res.ok) {
        const list = await res.json()
        setCameras(list)
        setSelectedCameraId(prev => {
          if (prev && list.some(c => c.id === prev)) return prev
          return list[0]?.id || null
        })
      }
    } catch (err) {}
  }, [])

  const fetchSnapshots = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/snapshots`)
      if (res.ok) {
        const data = await res.json()
        setSnapshots(data)
      }
    } catch (err) {}
  }, [])

  useEffect(() => {
    fetchCameras()
    fetchSnapshots()
    const interval = setInterval(fetchCameras, 900)
    return () => clearInterval(interval)
  }, [fetchCameras, fetchSnapshots])

  const handleSaveZones = async (cameraId, newZones) => {
    try {
      const res = await fetch(`${API_URL}/api/cameras/${encodeURIComponent(cameraId)}/zones`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newZones)
      })
      if (res.ok) {
        await fetchCameras()
      }
    } catch (err) {}
  }

  const handleAddCamera = async (payload) => {
    try {
      const res = await fetch(`${API_URL}/api/cameras`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      if (res.ok) {
        const data = await res.json()
        await fetchCameras()
        if (data?.camera?.id) {
          setSelectedCameraId(data.camera.id)
        }
      }
    } catch (err) {}
  }

  const handleUpdateCamera = async (cameraId, payload) => {
    try {
      const res = await fetch(`${API_URL}/api/cameras/${encodeURIComponent(cameraId)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      if (res.ok) {
        await fetchCameras()
      }
    } catch (err) {}
  }

  const handleDeleteCamera = async (cameraId) => {
    try {
      const res = await fetch(`${API_URL}/api/cameras/${encodeURIComponent(cameraId)}`, {
        method: 'DELETE'
      })
      if (res.ok) {
        await fetchCameras()
      }
    } catch (err) {}
  }

  const handleScanNetwork = async () => {
    setIsScanning(true)
    try {
      const res = await fetch(`${API_URL}/api/network/scan`, { method: 'POST' })
      if (res.ok) {
        setScanResults(await res.json())
      }
    } catch (err) {} finally {
      setIsScanning(false)
    }
  }

  const handleManualSnapshot = async (cameraId) => {
    setSnapshottingCameraId(cameraId)
    try {
      const res = await fetch(`${API_URL}/api/snapshot/manual`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note: 'Manual trigger', camera_id: cameraId })
      })
      if (res.ok) {
        await fetchSnapshots()
        setIsSnapshotsOpen(true)
      }
    } catch (err) {} finally {
      setSnapshottingCameraId(null)
    }
  }

  const handleDeleteSnapshot = async (filename) => {
    try {
      const res = await fetch(`${API_URL}/api/snapshots/${encodeURIComponent(filename)}`, {
        method: 'DELETE'
      })
      if (res.ok) {
        setSnapshots(prev => prev.filter(s => s.filename !== filename))
      }
    } catch (err) {}
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col text-slate-800">
      <Navbar
        cameras={cameras}
        onOpenSettings={() => { setSettingsTab('list'); setIsSettingsOpen(true) }}
        onOpenAddCamera={() => { setSettingsTab('add'); setIsSettingsOpen(true) }}
        onOpenSnapshots={() => setIsSnapshotsOpen(true)}
        snapshotCount={snapshots.length}
      />

      <main className="flex-1 max-w-[1720px] w-full mx-auto px-4 sm:px-6 py-5 space-y-4">
        {cameras.length > 0 ? (
          /* 2 CAMERAS SIDE-BY-SIDE IN A ROW TOGETHER */
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 items-start">
            {cameras.map((cam) => {
              const isSelected = cam.id === (selectedCameraId || cameras[0]?.id)
              return (
                <div
                  key={cam.id}
                  onClick={() => setSelectedCameraId(cam.id)}
                  className={`bg-white rounded-2xl border transition-all duration-200 overflow-hidden ${
                    isSelected
                      ? 'border-emerald-500 ring-2 ring-emerald-500/30 shadow-lg'
                      : 'border-slate-200 hover:border-slate-300 shadow-xs'
                  }`}
                >
                  {/* Camera Header Banner */}
                  <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between gap-3 bg-slate-50/70">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span
                        className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                          cam.connected ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'
                        }`}
                      />
                      <span className="font-bold text-sm text-slate-900 truncate">{cam.name}</span>
                      <span className="text-xs font-mono text-slate-400 bg-white border border-slate-200 px-2 py-0.5 rounded-md">
                        {cam.ip}
                      </span>
                      {cam.connected && (
                        <span className="text-xs font-mono text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-md">
                          {cam.fps} FPS
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {isSelected ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2.5 py-1 rounded-full bg-emerald-600 text-white shadow-2xs">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Selected</span>
                        </span>
                      ) : (
                        <span className="text-[11px] font-medium text-slate-500 hover:text-slate-700 px-2 py-1 rounded-md bg-white border border-slate-200">
                          Click to Select
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Complete Interactive Player for this camera */}
                  <div className="p-4">
                    <VideoZonePlayer
                      camera={cam}
                      streamUrl={`${API_URL}/api/cameras/${encodeURIComponent(cam.id)}/stream`}
                      apiUrl={API_URL}
                      liveZones={cam.zones || []}
                      zones={cam.saved_zones || []}
                      onSaveZones={(newZones) => handleSaveZones(cam.id, newZones)}
                      onManualSnapshot={() => handleManualSnapshot(cam.id)}
                      isSnapshotting={snapshottingCameraId === cam.id}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center space-y-4 max-w-lg mx-auto mt-8">
            <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto">
              <Video className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">No Cameras Added Yet</h2>
              <p className="text-xs text-slate-500 mt-1">
                Enter your camera IP, username, and password — port, protocol, and stream URL are auto-detected and stored securely in PostgreSQL.
              </p>
            </div>
            <div className="flex items-center justify-center gap-2.5 pt-1">
              <button
                onClick={() => { setSettingsTab('add'); setIsSettingsOpen(true) }}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm"
              >
                <Plus className="w-4 h-4" />
                <span>Add First Camera</span>
              </button>
              <button
                onClick={() => { setSettingsTab('list'); setIsSettingsOpen(true); handleScanNetwork() }}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-800"
              >
                <span>Scan Network</span>
              </button>
            </div>
          </div>
        )}
      </main>

      <SnapshotsDrawer
        isOpen={isSnapshotsOpen}
        onClose={() => setIsSnapshotsOpen(false)}
        snapshots={snapshots}
        onDeleteSnapshot={handleDeleteSnapshot}
        apiUrl={API_URL}
      />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        apiUrl={API_URL}
        cameras={cameras}
        initialTab={settingsTab}
        onAddCamera={handleAddCamera}
        onUpdateCamera={handleUpdateCamera}
        onDeleteCamera={handleDeleteCamera}
        onScanNetwork={handleScanNetwork}
        isScanning={isScanning}
        scanResults={scanResults}
      />
    </div>
  )
}
