import React from 'react'
import { CheckCircle2, AlertCircle, Layers, HardDrive, Wifi, Shield, Cpu } from 'lucide-react'

export default function StatsCards({ status, snapshotsCount, onOpenSnapshots, onOpenSettings }) {
  const zone = status?.zones?.[0]
  const isOccupied = zone?.occupied || false
  const detectedObjects = zone?.detected_objects || []

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
      
      {/* Card 1: Live Occupancy Radar */}
      <div className={`p-4 rounded-xl border transition-all ${
        isOccupied 
          ? 'bg-emerald-50/60 border-emerald-200/90 text-emerald-950' 
          : 'bg-rose-50/50 border-rose-200/80 text-rose-950'
      }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={`p-1.5 rounded-lg ${
              isOccupied ? 'bg-emerald-600 text-white' : 'bg-rose-600 text-white'
            }`}>
              {isOccupied ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
            </div>
            <div>
              <span className="text-[11px] font-semibold uppercase tracking-wider opacity-70">
                Marked Zone State
              </span>
              <h3 className="text-base font-bold tracking-tight">
                {isOccupied ? 'Thing Present (GREEN)' : 'Zone Empty (RED)'}
              </h3>
            </div>
          </div>
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
            isOccupied ? 'bg-emerald-200/70 text-emerald-800' : 'bg-rose-200/60 text-rose-700'
          }`}>
            {isOccupied ? 'Occupied' : 'Clear'}
          </span>
        </div>

        <div className="mt-3 text-xs opacity-80 flex flex-wrap gap-1.5">
          {detectedObjects.length > 0 ? (
            detectedObjects.map((o, idx) => (
              <span key={idx} className="bg-white/80 border border-emerald-300/50 px-2 py-0.5 rounded-md font-medium">
                {o.label} ({Math.round(o.confidence * 100)}%)
              </span>
            ))
          ) : (
            <span>No objects detected inside the marked square</span>
          )}
        </div>
      </div>

      {/* Card 2: Stored Captures */}
      <div
        onClick={onOpenSnapshots}
        className="p-4 rounded-xl bg-white border border-slate-200/90 hover:border-slate-300 transition-all cursor-pointer shadow-2xs group"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-slate-100 text-slate-700 group-hover:bg-slate-200/80 transition-colors">
              <HardDrive className="w-4 h-4" />
            </div>
            <div>
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                Stored Things
              </span>
              <h3 className="text-base font-bold text-slate-900 tracking-tight">
                {snapshotsCount} Snapshots
              </h3>
            </div>
          </div>
          <span className="text-xs font-medium text-slate-500 group-hover:text-slate-900 group-hover:underline">
            View All &rarr;
          </span>
        </div>
        <p className="mt-3 text-xs text-slate-500">
          Auto-saves snapshots when objects enter the square. Click to view history.
        </p>
      </div>

      {/* Card 3: Camera Connection */}
      <div
        onClick={onOpenSettings}
        className="p-4 rounded-xl bg-white border border-slate-200/90 hover:border-slate-300 transition-all cursor-pointer shadow-2xs group"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-slate-100 text-slate-700 group-hover:bg-slate-200/80 transition-colors">
              <Wifi className="w-4 h-4" />
            </div>
            <div>
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                CP PLUS Hardware
              </span>
              <h3 className="text-base font-bold text-slate-900 tracking-tight">
                {status?.connected ? 'Online & Linked' : 'Connect TP-Link Wi-Fi'}
              </h3>
            </div>
          </div>
          <span className="text-xs font-medium text-slate-500 group-hover:text-slate-900 group-hover:underline">
            Setup &rarr;
          </span>
        </div>
        <p className="mt-3 text-xs text-slate-500">
          Connect PC to <span className="font-semibold text-slate-700">TP-Link_B2B7</span> (Pass: <code className="bg-slate-100 px-1 py-0.5 rounded text-slate-700">17009690</code>)
        </p>
      </div>

    </div>
  )
}
