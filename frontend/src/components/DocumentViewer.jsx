import React, { useState } from 'react'
import { Download, FileText, Image as ImageIcon } from 'lucide-react'
import { getVersions, downloadFile, sendMessage } from '../api/client'
import toast from 'react-hot-toast'
import InsertImageModal from './InsertImageModal.jsx'

function formatSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

function ArtifactCard({
  artifact,
  artifactId,
  type,
  sessionId,
  uploadedFiles = [],
  onImageInserted,
  onEditResponse,
}) {
  const [versions, setVersions] = useState([])
  const [showVersions, setShowVersions] = useState(false)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editQuery, setEditQuery] = useState('')
  const [isEditing, setIsEditing] = useState(false)

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

  const handleQuickEdit = async () => {
    if (!editQuery.trim() || isEditing) return
    setIsEditing(true)
    const toastId = toast.loading(`Applying edit to ${tag}...`)
    try {
      const fileIds = uploadedFiles.map(f => f.file_id)
      const result = await sendMessage(editQuery, sessionId, fileIds)
      if (onEditResponse) onEditResponse(result)
      toast.success(`Successfully updated ${tag}!`, { id: toastId })
      setEditQuery('')
    } catch (e) {
      toast.error(`Edit failed: ${e.response?.data?.detail || e.message}`, { id: toastId })
    } finally {
      setIsEditing(false)
    }
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

      {/* Quick Edit Section */}
      {artifactId && (
        <div style={{ marginTop: 12, padding: 8, background: 'var(--bg-deep)', borderRadius: 6, border: '1px solid var(--border)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>✏️ Quick Edit via AI</div>
          <input
            type="text"
            value={editQuery}
            onChange={(e) => setEditQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleQuickEdit()}
            placeholder={`e.g. "Add an executive summary to this ${tag}"`}
            disabled={isEditing}
            style={{
              width: '100%',
              padding: '6px 8px',
              fontSize: 12,
              borderRadius: 4,
              border: '1px solid var(--border)',
              background: 'var(--bg-surface)',
              color: 'var(--text-primary)',
              marginBottom: 4
            }}
          />
          <button 
            className="btn btn-secondary" 
            onClick={handleQuickEdit}
            disabled={isEditing || !editQuery.trim()}
            style={{ width: '100%', justifyContent: 'center', padding: '4px', fontSize: 11 }}
          >
            {isEditing ? 'Applying...' : 'Apply Edit'}
          </button>
        </div>
      )}

      {isDoc && artifactId && (
        <button
          className="btn btn-secondary"
          onClick={() => setIsModalOpen(true)}
          style={{ width: '100%', justifyContent: 'center', marginTop: 6, background: 'var(--accent-dim)', border: '1px solid var(--accent)' }}
        >
          <ImageIcon size={13} style={{ color: 'var(--accent-light)' }} /> 🖼️ Insert Image
        </button>
      )}

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

      {isDoc && artifactId && (
        <InsertImageModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          artifactId={artifactId}
          sessionId={sessionId}
          uploadedFiles={uploadedFiles}
          onImageInserted={onImageInserted}
        />
      )}
    </div>
  )
}

export default function DocumentViewer({
  generatedDoc,
  generatedPpt,
  docArtifactId,
  pptArtifactId,
  sessionId,
  uploadedFiles,
  onImageInserted,
}) {
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
          sessionId={sessionId}
          uploadedFiles={uploadedFiles}
          onImageInserted={onImageInserted}
        />
      )}
      {generatedPpt && (
        <ArtifactCard
          artifact={generatedPpt}
          artifactId={pptArtifactId}
          type="pptx"
          sessionId={sessionId}
          uploadedFiles={uploadedFiles}
          onImageInserted={onImageInserted}
        />
      )}
    </div>
  )
}
