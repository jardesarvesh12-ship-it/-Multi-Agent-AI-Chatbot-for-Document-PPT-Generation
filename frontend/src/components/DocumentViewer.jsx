import React, { useState, useEffect } from 'react'
import { Download, FileText, Presentation, ExternalLink } from 'lucide-react'
import { getVersions, downloadFile } from '../api/client'
import toast from 'react-hot-toast'

function formatSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

function ArtifactCard({ artifact, artifactId, type }) {
  const [versions, setVersions] = useState([])
  const [showVersions, setShowVersions] = useState(false)

  const isDoc = type === 'docx'
  const icon = isDoc ? '📄' : '📊'
  const tag = isDoc ? 'DOCX' : 'PPTX'
  const tagClass = isDoc ? 'tag-docx' : 'tag-pptx'

  const loadVersions = async () => {
    if (!artifactId) return
    try {
      const data = await getVersions(artifactId)
      setVersions(data.versions || [])
      setShowVersions(true)
    } catch {
      toast.error('Could not load version history')
    }
  }

  const handleDownload = () => {
    downloadFile(artifact.filename)
    toast.success(`Downloading ${artifact.filename}`)
  }

  return (
    <div className="artifact-card">
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <span style={{ fontSize: 24 }}>{icon}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span className={`tag ${tagClass}`}>{tag}</span>
          </div>
          <div className="artifact-name" style={{ marginTop: 2 }}>
            {artifact.filename}
          </div>
          <div className="artifact-meta">{formatSize(artifact.size_bytes)}</div>
        </div>
      </div>

      <button className="download-btn" onClick={handleDownload}>
        <Download size={12} /> Download {tag}
      </button>

      {artifactId && (
        <button
          className="btn"
          onClick={loadVersions}
          style={{ width: '100%', justifyContent: 'center', marginTop: 6 }}
        >
          📋 Version History
        </button>
      )}

      {showVersions && versions.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>
            {versions.length} version(s)
          </div>
          <div className="version-list">
            {versions.slice().reverse().map((v, i) => (
              <div
                key={v.version_number}
                className={`version-item ${i === 0 ? 'active' : ''}`}
                onClick={() => downloadFile(`${v.artifact_id}_v${v.version_number}.${v.file_type}`)}
              >
                <span className="version-num">v{v.version_number}</span>
                <span className="version-desc">{v.description || 'Generated'}</span>
                <span className="version-date">
                  {new Date(v.created_at).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function DocumentViewer({ generatedDoc, generatedPpt, docArtifactId, pptArtifactId }) {
  if (!generatedDoc && !generatedPpt) {
    return (
      <div className="empty-state">
        <div style={{ fontSize: 28, marginBottom: 8 }}>📁</div>
        <div>Generated files appear here</div>
        <div style={{ fontSize: 11, marginTop: 4 }}>Ask the AI to generate a document or presentation</div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: 16 }}>
      {generatedDoc && (
        <ArtifactCard
          artifact={generatedDoc}
          artifactId={docArtifactId}
          type="docx"
        />
      )}
      {generatedPpt && (
        <ArtifactCard
          artifact={generatedPpt}
          artifactId={pptArtifactId}
          type="pptx"
        />
      )}
    </div>
  )
}
