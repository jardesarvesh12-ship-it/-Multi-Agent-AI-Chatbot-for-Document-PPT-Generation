import React, { useState, useEffect } from 'react'
import { getVersions, downloadFile } from '../api/client'
import toast from 'react-hot-toast'

export default function VersionHistory({ docArtifactId, pptArtifactId }) {
  const [docVersions, setDocVersions] = useState([])
  const [pptVersions, setPptVersions] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        if (docArtifactId) {
          const d = await getVersions(docArtifactId)
          setDocVersions(d.versions || [])
        }
        if (pptArtifactId) {
          const p = await getVersions(pptArtifactId)
          setPptVersions(p.versions || [])
        }
      } catch {
        // Versions may not exist yet
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [docArtifactId, pptArtifactId])

  const handleDownload = (v) => {
    const filename = `${v.artifact_id}_v${v.version_number}.${v.file_type}`
    downloadFile(filename)
    toast.success(`Downloading v${v.version_number}`)
  }

  const allVersions = [
    ...docVersions.map(v => ({ ...v, label: '📄 DOCX' })),
    ...pptVersions.map(v => ({ ...v, label: '📊 PPTX' })),
  ].sort((a, b) => new Date(b.created_at) - new Date(a.created_at))

  if (!docArtifactId && !pptArtifactId) {
    return (
      <div className="empty-state">
        <div style={{ fontSize: 28, marginBottom: 8 }}>📋</div>
        <div>No version history yet</div>
        <div style={{ fontSize: 11, marginTop: 4 }}>
          Versions are tracked when documents are generated or edited
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="empty-state">
        <div className="trace-spinner" style={{ margin: '0 auto 8px' }} />
        Loading versions…
      </div>
    )
  }

  return (
    <div style={{ padding: 16 }}>
      <div className="version-list">
        {allVersions.map((v, i) => (
          <div
            key={`${v.artifact_id}-${v.version_number}`}
            className={`version-item ${i === 0 ? 'active' : ''}`}
            onClick={() => handleDownload(v)}
            title="Click to download this version"
          >
            <span className="version-num">v{v.version_number}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span>{v.label}</span>
              </div>
              <div className="version-desc">{v.description || 'Generated'}</div>
            </div>
            <span className="version-date">
              {new Date(v.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
