import React, { useState, useCallback } from 'react'
import ChatPanel from './components/ChatPanel.jsx'
import FileUploader from './components/FileUploader.jsx'
import AgentTracePanel from './components/AgentTracePanel.jsx'
import DocumentViewer from './components/DocumentViewer.jsx'
import VersionHistory from './components/VersionHistory.jsx'

const SESSION_ID = 'session_' + Math.random().toString(36).slice(2, 10)

export default function App() {
  // Uploaded file IDs (from backend)
  const [uploadedFileIds, setUploadedFileIds] = useState([])
  const [uploadedFiles, setUploadedFiles] = useState([])

  // Agent trace
  const [agentTrace, setAgentTrace] = useState([])

  // Generated artifacts
  const [generatedDoc, setGeneratedDoc] = useState(null)
  const [generatedPpt, setGeneratedPpt] = useState(null)
  const [docArtifactId, setDocArtifactId] = useState(null)
  const [pptArtifactId, setPptArtifactId] = useState(null)
  const [citations, setCitations] = useState([])

  // Right panel tab
  const [rightTab, setRightTab] = useState('artifacts') // artifacts | trace | versions

  const handleFilesUploaded = useCallback((results) => {
    const ids = results.map(r => r.file_id)
    setUploadedFileIds(prev => [...prev, ...ids])
    setUploadedFiles(prev => [...prev, ...results])
  }, [])

  const handleChatResponse = useCallback((result) => {
    // Update agent trace
    if (result.agent_trace) setAgentTrace(result.agent_trace)

    // Update generated files
    if (result.generated_doc) setGeneratedDoc(result.generated_doc)
    if (result.generated_ppt) setGeneratedPpt(result.generated_ppt)
    if (result.doc_artifact_id) setDocArtifactId(result.doc_artifact_id)
    if (result.ppt_artifact_id) setPptArtifactId(result.ppt_artifact_id)
    if (result.citations?.length) setCitations(result.citations)
  }, [])

  return (
    <div className="app-layout">
      {/* ── Header ── */}
      <header className="header">
        <div className="header-logo">
          <div className="logo-icon">⚡</div>
          <span>AgentDoc</span>
        </div>
        <span className="header-badge">Multi-Agent AI</span>
        <div className="header-spacer" />
        <div className="header-status">
          <div className="status-dot" />
          <span>System Online</span>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {uploadedFiles.length > 0 && (
            <span>{uploadedFiles.length} file(s) loaded</span>
          )}
        </div>
      </header>

      {/* ── Left Panel: Upload + Knowledge ── */}
      <div className="left-panel">
        <div className="panel-header">
          📎 Templates & Files
        </div>
        <FileUploader onFilesUploaded={handleFilesUploaded} />

        {/* Uploaded files list */}
        {uploadedFiles.length > 0 && (
          <>
            <div className="panel-header" style={{ borderTop: '1px solid var(--border)' }}>
              ✅ Uploaded ({uploadedFiles.length})
            </div>
            <div style={{ padding: '8px 16px' }}>
              {uploadedFiles.map((f, i) => {
                const ext = f.file_type
                const icons = { docx: '📄', pdf: '📑', pptx: '📊', png: '🖼️', jpg: '🖼️' }
                return (
                  <div key={i} className="file-item" style={{ marginBottom: 4 }}>
                    <span className="file-item-icon">{icons[ext] || '📁'}</span>
                    <span className="file-item-name">{f.filename}</span>
                    <span className={`tag tag-${ext === 'pptx' ? 'pptx' : 'docx'}`}>
                      {ext.toUpperCase()}
                    </span>
                  </div>
                )
              })}
            </div>
          </>
        )}

        {/* Citations */}
        {citations.length > 0 && (
          <>
            <div className="panel-header" style={{ borderTop: '1px solid var(--border)' }}>
              📚 Sources ({citations.length})
            </div>
            <div style={{ padding: '8px 16px', fontSize: 11, color: 'var(--text-secondary)' }}>
              {citations.slice(0, 8).map((c, i) => (
                <div key={i} style={{ padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
                  [{i + 1}] {c}
                </div>
              ))}
              {citations.length > 8 && (
                <div style={{ padding: 4, color: 'var(--text-muted)' }}>
                  +{citations.length - 8} more…
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* ── Center: Chat Panel ── */}
      <ChatPanel
        sessionId={SESSION_ID}
        uploadedFileIds={uploadedFileIds}
        onChatResponse={handleChatResponse}
      />

      {/* ── Right Panel: Artifacts + Trace + Versions ── */}
      <div className="right-panel">
        {/* Tab bar */}
        <div style={{
          display: 'flex',
          borderBottom: '1px solid var(--border)',
        }}>
          {[
            { key: 'artifacts', label: '📁 Files', },
            { key: 'trace', label: '🤖 Agents', },
            { key: 'versions', label: '📋 History', },
          ].map(tab => (
            <button
              key={tab.key}
              className="btn"
              style={{
                flex: 1,
                border: 'none',
                borderRadius: 0,
                borderBottom: rightTab === tab.key ? '2px solid var(--accent)' : '2px solid transparent',
                color: rightTab === tab.key ? 'var(--accent-light)' : 'var(--text-muted)',
                background: 'transparent',
                fontSize: 11,
                padding: '10px 8px',
                justifyContent: 'center',
              }}
              onClick={() => setRightTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          {rightTab === 'artifacts' && (
            <DocumentViewer
              generatedDoc={generatedDoc}
              generatedPpt={generatedPpt}
              docArtifactId={docArtifactId}
              pptArtifactId={pptArtifactId}
              sessionId={SESSION_ID}
              uploadedFiles={uploadedFiles}
              onImageInserted={(newDoc) => setGeneratedDoc(newDoc)}
            />
          )}
          {rightTab === 'trace' && (
            <AgentTracePanel trace={agentTrace} />
          )}
          {rightTab === 'versions' && (
            <VersionHistory
              docArtifactId={docArtifactId}
              pptArtifactId={pptArtifactId}
            />
          )}
        </div>
      </div>
    </div>
  )
}
