import React, { useState } from 'react'
import { X, Download, Trash2, Calendar, Image as ImageIcon, ExternalLink } from 'lucide-react'

export default function SnapshotsDrawer({
  isOpen,
  onClose,
  snapshots,
  onDeleteSnapshot,
  apiUrl
}) {
  const [selectedSnapshot, setSelectedSnapshot] = useState(null)

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        onClick={onClose}
        className="absolute inset-0 bg-slate-900/25 backdrop-blur-xs transition-opacity"
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-white shadow-2xl border-l border-slate-200 flex flex-col">
          
          {/* Header */}
          <div className="px-6 py-4 border-b border-slate-200/80 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="p-1.5 rounded-lg bg-slate-100 text-slate-700">
                <ImageIcon className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-slate-900">Stored Captures</h2>
                <p className="text-[11px] text-slate-500">{snapshots.length} snapshots recorded</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* List of Snapshots */}
          <div className="flex-1 overflow-y-auto p-5 space-y-3">
            {snapshots.length === 0 ? (
              <div className="h-64 flex flex-col items-center justify-center text-center p-6 text-slate-400">
                <ImageIcon className="w-10 h-10 stroke-[1.5] mb-2 text-slate-300" />
                <p className="text-xs font-medium text-slate-600">No snapshots stored yet</p>
                <p className="text-[11px] text-slate-400 mt-1 max-w-xs">
                  Snapshots are automatically saved whenever a thing enters the marked zone, or when you click "Snapshot".
                </p>
              </div>
            ) : (
              snapshots.map((item) => (
                <div
                  key={item.filename}
                  className="group p-3 rounded-xl border border-slate-200/80 hover:border-slate-300 bg-white hover:bg-slate-50/50 transition-all flex items-center gap-3.5 shadow-2xs"
                >
                  {/* Thumbnail */}
                  <img
                    src={`${apiUrl}${item.url}`}
                    alt={item.filename}
                    onClick={() => setSelectedSnapshot(item)}
                    className="w-16 h-12 object-cover rounded-lg bg-slate-100 border border-slate-200 cursor-pointer group-hover:scale-105 transition-transform"
                  />

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <p
                      onClick={() => setSelectedSnapshot(item)}
                      className="text-xs font-medium text-slate-800 truncate cursor-pointer hover:text-emerald-600"
                    >
                      {item.filename}
                    </p>
                    <div className="flex items-center gap-2 mt-1 text-[11px] text-slate-400">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {item.timestamp}
                      </span>
                      <span>•</span>
                      <span>{item.size_kb} KB</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1 opacity-80 group-hover:opacity-100 transition-opacity">
                    <a
                      href={`${apiUrl}${item.url}`}
                      download={item.filename}
                      target="_blank"
                      rel="noopener noreferrer"
                      title="Download image"
                      className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors"
                    >
                      <Download className="w-3.5 h-3.5" />
                    </a>
                    <button
                      onClick={() => onDeleteSnapshot(item.filename)}
                      title="Delete snapshot"
                      className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Footer */}
          <div className="p-4 border-t border-slate-200/80 bg-slate-50/60 text-center">
            <span className="text-[11px] text-slate-400">
              Files are saved in <code className="bg-slate-200/70 px-1 py-0.5 rounded text-slate-700">backend/storage/snapshots/</code>
            </span>
          </div>

        </div>
      </div>

      {/* Full Size Modal Viewer */}
      {selectedSnapshot && (
        <div className="fixed inset-0 z-60 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-3xl w-full overflow-hidden shadow-2xl border border-slate-200">
            <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h3 className="text-xs font-semibold text-slate-900">{selectedSnapshot.filename}</h3>
                <p className="text-[11px] text-slate-500">{selectedSnapshot.timestamp}</p>
              </div>
              <div className="flex items-center gap-2">
                <a
                  href={`${apiUrl}${selectedSnapshot.url}`}
                  download={selectedSnapshot.filename}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-900 text-white hover:bg-slate-800"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download</span>
                </a>
                <button
                  onClick={() => setSelectedSnapshot(null)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
            <div className="bg-slate-950 p-2 flex items-center justify-center">
              <img
                src={`${apiUrl}${selectedSnapshot.url}`}
                alt="Snapshot view"
                className="max-h-[70vh] object-contain rounded-lg"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
