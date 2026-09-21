import React, { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, X, FileText, Presentation, Image, File } from 'lucide-react'
import toast from 'react-hot-toast'
import { uploadFiles } from '../api/client'

const FILE_ICONS = {
  docx: '📄', pdf: '📑', pptx: '📊', ppt: '📊',
  png: '🖼️', jpg: '🖼️', jpeg: '🖼️', tiff: '🖼️',
}

const formatSize = (bytes) => {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

export default function FileUploader({ onFilesUploaded }) {
  const [localFiles, setLocalFiles] = useState([])   // {file, preview}
  const [uploading, setUploading] = useState(false)

  const onDrop = useCallback((acceptedFiles) => {
    const newFiles = acceptedFiles.map(f => ({
      file: f,
      id: Math.random().toString(36).slice(2),
    }))
    setLocalFiles(prev => [...prev, ...newFiles])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
      'image/png': ['.png'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/tiff': ['.tiff'],
    },
    maxSize: 50 * 1024 * 1024,
  })

  const removeFile = (id) => {
    setLocalFiles(prev => prev.filter(f => f.id !== id))
  }

  const handleUpload = async () => {
    if (localFiles.length === 0) return
    setUploading(true)
    try {
      const files = localFiles.map(lf => lf.file)
      const result = await uploadFiles(files)
      toast.success(`${result.length} file(s) uploaded successfully!`)
      onFilesUploaded(result)
      setLocalFiles([])
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="panel-section" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div
        {...getRootProps()}
        className={`dropzone ${isDragActive ? 'active' : ''}`}
      >
        <input {...getInputProps()} />
        <div className="dropzone-icon">⬆️</div>
        <div className="dropzone-text">
          {isDragActive ? 'Drop files here…' : 'Drag & drop templates'}
        </div>
        <div className="dropzone-hint">PDF, DOCX, PPTX, Images — max 50MB</div>
      </div>

      {localFiles.length > 0 && (
        <>
          <div className="file-list">
            {localFiles.map(({ file, id }) => {
              const ext = file.name.split('.').pop().toLowerCase()
              return (
                <div key={id} className="file-item">
                  <span className="file-item-icon">{FILE_ICONS[ext] || '📁'}</span>
                  <span className="file-item-name" title={file.name}>{file.name}</span>
                  <span className="file-item-size">{formatSize(file.size)}</span>
                  <button className="file-remove-btn" onClick={() => removeFile(id)}>
                    <X size={12} />
                  </button>
                </div>
              )
            })}
          </div>

          <button
            className="btn btn-primary"
            onClick={handleUpload}
            disabled={uploading}
            style={{ width: '100%', justifyContent: 'center' }}
          >
            {uploading ? (
              <><div className="trace-spinner" style={{ borderColor: 'rgba(255,255,255,0.3)', borderTopColor: 'white' }} /> Uploading…</>
            ) : (
              <><Upload size={13} /> Upload {localFiles.length} file(s)</>
            )}
          </button>
        </>
      )}
    </div>
  )
}
