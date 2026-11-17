import React, { useState, useEffect, useCallback } from 'react'
import Navbar from './components/Navbar'
import StatsCards from './components/StatsCards'
import VideoZonePlayer from './components/VideoZonePlayer'
import SnapshotsDrawer from './components/SnapshotsDrawer'
import SettingsModal from './components/SettingsModal'
import { Info, Wifi, Check, ExternalLink } from 'lucide-react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function App() {
  const [status, setStatus] = useState(null)
  const [zones, setZones] = useState([])
  const [snapshots, setSnapshots] = useState([])
  const [config, setConfig] = useState(null)
  
  // Modals state
  const [isSnapshotsOpen, setIsSnapshotsOpen] = useState(false)
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [isSnapshotting, setIsSnapshotting] = useState(false)
  const [isScanning, setIsScanning] = useState(false)
  const [scanResults, setScanResults] = useState(null)
  const [showGuideBanner, setShowGuideBanner] = useState(true)

  // Fetch system status
  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/status`)
      if (res.ok) {
        const data = await res.json()
        setStatus(data)
      }
    } catch (err) {
      // Backend may be starting up
    }
  }, [])

  // Fetch active zones
  const fetchZones = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/zones`)
      if (res.ok) {
        const data = await res.json()
        setZones(data)
      }
    } catch (err) {
      console.error('Failed to fetch zones', err)
    }
  }, [])

  // Fetch snapshots
  const fetchSnapshots = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/snapshots`)
      if (res.ok) {
        const data = await res.json()
        setSnapshots(data)
      }
    } catch (err) {
      console.error('Failed to fetch snapshots', err)
    }
  }, [])

  // Fetch camera config
  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/camera/config`)
      if (res.ok) {
        const data = await res.json()
        setConfig(data)
      }
    } catch (err) {
      console.error('Failed to fetch config', err)
    }
  }, [])

  // Initial load
  useEffect(() => {
    fetchStatus()
    fetchZones()
    fetchSnapshots()
    fetchConfig()

    // Poll status every 800ms for real-time reactivity
    const interval = setInterval(fetchStatus, 800)
    return () => clearInterval(interval)
  }, [fetchStatus, fetchZones, fetchSnapshots, fetchConfig])

  // Save new zone box
  const handleSaveZones = async (newZones) => {
    try {
      const res = await fetch(`${API_URL}/api/zones`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newZones)
      })
      if (res.ok) {
        const data = await res.json()
        setZones(data.zones)
        fetchStatus()
      }
    } catch (err) {
      console.error('Error updating zones:', err)
    }
  }

  // Trigger manual snapshot
  const handleManualSnapshot = async () => {
    setIsSnapshotting(true)
    try {
      const res = await fetch(`${API_URL}/api/snapshot/manual`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note: 'Manual trigger' })
      })
      if (res.ok) {
        await fetchSnapshots()
        setIsSnapshotsOpen(true)
      }
    } catch (err) {
      console.error('Failed to take snapshot:', err)
    } finally {
      setIsSnapshotting(false)
    }
  }

  // Delete snapshot
  const handleDeleteSnapshot = async (filename) => {
    try {
      const res = await fetch(`${API_URL}/api/snapshots/${encodeURIComponent(filename)}`, {
        method: 'DELETE'
      })
      if (res.ok) {
        setSnapshots(prev => prev.filter(s => s.filename !== filename))
      }
    } catch (err) {
      console.error('Failed to delete snapshot', err)
    }
  }

  // Save camera settings
  const handleSaveConfig = async (newConfig) => {
    try {
      const res = await fetch(`${API_URL}/api/camera/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newConfig)
      })
      if (res.ok) {
        fetchConfig()
        fetchStatus()
      }
    } catch (err) {
      console.error('Error saving config:', err)
    }
  }

  // Scan network for camera
  const handleScanNetwork = async () => {
    setIsScanning(true)
    try {
      const res = await fetch(`${API_URL}/api/network/scan`, {
        method: 'POST'
      })
      if (res.ok) {
        const data = await res.json()
        setScanResults(data)
      }
    } catch (err) {
      console.error('Scan failed:', err)
    } finally {
      setIsScanning(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col text-slate-800">
      
      {/* Top Navigation */}
      <Navbar
        status={status}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenSnapshots={() => setIsSnapshotsOpen(true)}
        snapshotCount={snapshots.length}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6">
        
        {/* Hardware Quick-Guide Alert Banner */}
        {showGuideBanner && (
          <div className="mb-6 p-4 rounded-xl bg-white border border-slate-200/90 shadow-2xs flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-emerald-50 text-emerald-600 shrink-0">
                <Wifi className="w-4 h-4" />
              </div>
              <div className="text-xs">
                <span className="font-semibold text-slate-900 block mb-0.5">
                  CP PLUS & TP-Link Router Connection Guide
                </span>
                <p className="text-slate-500 leading-relaxed">
                  1. Camera is powered by 12V. 
                  2. To stream the camera directly, connect your PC to Wi-Fi <strong className="text-slate-700">TP-Link_B2B7</strong> (Password: <code className="bg-slate-100 px-1 py-0.5 rounded text-slate-800">17009690</code>).
                  3. If you want to test right now before switching Wi-Fi, the system is in <strong className="text-slate-700">Demo Simulation Mode</strong> so you can draw boxes and see Green/Red detection instantly!
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => setIsSettingsOpen(true)}
                className="px-3 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200/80 rounded-lg transition-colors"
              >
                Open Camera Setup
              </button>
              <button
                onClick={() => setShowGuideBanner(false)}
                className="text-slate-400 hover:text-slate-600 text-xs px-2 py-1"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {/* Stats and Occupancy Status Cards */}
        <StatsCards
          status={status}
          snapshotsCount={snapshots.length}
          onOpenSnapshots={() => setIsSnapshotsOpen(true)}
          onOpenSettings={() => setIsSettingsOpen(true)}
        />

        {/* Interactive Video Feed & Zone Drawing Area */}
        <VideoZonePlayer
          streamUrl={`${API_URL}/api/stream`}
          status={status}
          zones={zones}
          onSaveZones={handleSaveZones}
          onManualSnapshot={handleManualSnapshot}
          isSnapshotting={isSnapshotting}
        />

      </main>

      {/* Snapshots Sidebar / Drawer */}
      <SnapshotsDrawer
        isOpen={isSnapshotsOpen}
        onClose={() => setIsSnapshotsOpen(false)}
        snapshots={snapshots}
        onDeleteSnapshot={handleDeleteSnapshot}
        apiUrl={API_URL}
      />

      {/* Camera & Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        config={config}
        onSaveConfig={handleSaveConfig}
        onScanNetwork={handleScanNetwork}
        isScanning={isScanning}
        scanResults={scanResults}
      />

      {/* Footer */}
      <footer className="border-t border-slate-200/80 bg-white/60 py-3.5 text-center text-xs text-slate-400">
        <span>Camera Thing Detector • React + FastAPI + YOLOv8 • CP PLUS RTSP Stream Ready</span>
      </footer>

    </div>
  )
}
