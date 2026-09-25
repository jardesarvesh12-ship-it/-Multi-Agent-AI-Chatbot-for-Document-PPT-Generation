import React, { useState, useEffect } from 'react'
import { X, Upload, Image as ImageIcon, Check, Loader2, Award, FileText } from 'lucide-react'
import toast from 'react-hot-toast'
import { getDocumentSections, insertImageToDoc } from '../api/client'

export default function InsertImageModal({
  isOpen,
  onClose,
  artifactId,
  sessionId,
  uploadedFiles = [],
  onImageInserted,
}) {
  const [imageCategory, setImageCategory] = useState('logo') // 'image' | 'logo'
  const [sourceType, setSourceType] = useState('upload') // 'upload' | 'existing'
  const [selectedFile, setSelectedFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [existingFilename, setExistingFilename] = useState('')

  const [sections, setSections] = useState([])
  const [placementTarget, setPlacementTarget] = useState('header_logo') // 'header_logo' | 'section'
  const [targetSection, setTargetSection] = useState('')
  const [caption, setCaption] = useState('')
  const [align, setAlign] = useState('left')
  const [widthInches, setWidthInches] = useState(1.8)

  const [loadingSections, setLoadingSections] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // Filter image files from uploaded files
  const imageFiles = uploadedFiles.filter(f => {
    const ext = (f.file_type || f.filename?.split('.').pop() || '').toLowerCase()
    return ['png', 'jpg', 'jpeg', 'webp', 'tiff', 'gif', 'bmp', 'svg'].includes(ext)
  })

  // Load section headings when modal opens
  useEffect(() => {
    if (!isOpen || !artifactId) return

    async function loadSections() {
      setLoadingSections(true)
      try {
        const data = await getDocumentSections(artifactId)
        setSections(data.sections || [])
        if (data.sections && data.sections.length > 0) {
          setTargetSection(data.sections[0])
        }
      } catch (err) {
        console.warn('Could not load document sections:', err)
      } finally {
        setLoadingSections(false)
      }
    }

    loadSections()
  }, [isOpen, artifactId])

  // Adjust defaults based on Category (Image vs Logo)
  const handleCategoryChange = (cat) => {
    setImageCategory(cat)
    if (cat === 'logo') {
      setWidthInches(1.8)
      setAlign('left')
      setPlacementTarget('header_logo')
      setCaption('')
    } else {
      setWidthInches(5.0)
      setAlign('center')
      setPlacementTarget('section')
    }
  }

  // Handle file selection for upload
  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setSelectedFile(file)
    setPreviewUrl(URL.createObjectURL(file))
  }

  // Handle submit
  const handleSubmit = async (e) => {
    e.preventDefault()

    if (sourceType === 'upload' && !selectedFile) {
      toast.error('Please choose an image or logo file to upload')
      return
    }
    if (sourceType === 'existing' && !existingFilename) {
      toast.error('Please select an existing image/logo file')
      return
    }

    setSubmitting(true)
    try {
      const formData = new FormData()
      formData.append('artifact_id', artifactId)
      if (sessionId) formData.append('session_id', sessionId)
      formData.append('is_logo', imageCategory === 'logo' ? 'true' : 'false')
      formData.append('placement_target', placementTarget)

      if (placementTarget === 'section' && targetSection) {
        formData.append('section_heading', targetSection)
      }
      if (caption) formData.append('caption', caption)
      formData.append('align', align)
      formData.append('width_inches', widthInches)

      if (sourceType === 'upload' && selectedFile) {
        formData.append('image_file', selectedFile)
      } else if (sourceType === 'existing' && existingFilename) {
        formData.append('existing_image_filename', existingFilename)
      }

      const res = await insertImageToDoc(formData)
      toast.success(res.message || `${imageCategory === 'logo' ? 'Company Logo' : 'Image'} inserted successfully!`)

      if (onImageInserted) {
        onImageInserted(res.generated_doc)
      }
      onClose()
    } catch (err) {
      console.error(err)
      toast.error(err.response?.data?.detail || 'Failed to insert image/logo')
    } finally {
      setSubmitting(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-container" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div className="modal-title">
            <span className="modal-title-icon">{imageCategory === 'logo' ? '🏢' : '🖼️'}</span>
            <span>Insert {imageCategory === 'logo' ? 'Company Logo / Brand Symbol' : 'Image'}</span>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body">
          {/* Category Switcher: Logo vs Image */}
          <div className="form-group">
            <label className="form-label">Type of Graphic</label>
            <div className="category-toggle">
              <button
                type="button"
                className={`category-btn ${imageCategory === 'logo' ? 'active' : ''}`}
                onClick={() => handleCategoryChange('logo')}
              >
                🏢 Company Logo / Brand Symbol
              </button>
              <button
                type="button"
                className={`category-btn ${imageCategory === 'image' ? 'active' : ''}`}
                onClick={() => handleCategoryChange('image')}
              >
                🖼️ Regular Document Image
              </button>
            </div>
          </div>

          {/* Source Selector Tabs */}
          <div className="tab-buttons">
            <button
              type="button"
              className={`tab-btn ${sourceType === 'upload' ? 'active' : ''}`}
              onClick={() => setSourceType('upload')}
            >
              <Upload size={14} /> Upload New {imageCategory === 'logo' ? 'Logo' : 'File'}
            </button>
            {imageFiles.length > 0 && (
              <button
                type="button"
                className={`tab-btn ${sourceType === 'existing' ? 'active' : ''}`}
                onClick={() => setSourceType('existing')}
              >
                <ImageIcon size={14} /> From Uploaded ({imageFiles.length})
              </button>
            )}
          </div>

          {/* Source 1: Upload File */}
          {sourceType === 'upload' && (
            <div className="form-group">
              <label className="form-label">
                {imageCategory === 'logo' ? 'Logo / Symbol File (PNG, SVG, JPG, WEBP)' : 'Image File (PNG, JPG, WEBP)'}
              </label>
              <div className="file-input-wrapper">
                <input
                  type="file"
                  accept="image/png, image/jpeg, image/webp, image/svg+xml, image/tiff"
                  onChange={handleFileChange}
                  id="image-file-input"
                  style={{ display: 'none' }}
                />
                <label htmlFor="image-file-input" className="file-input-dropzone">
                  {selectedFile ? (
                    <div className="preview-container">
                      <img src={previewUrl} alt="Preview" className="image-preview" />
                      <div className="preview-meta">{selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)</div>
                    </div>
                  ) : (
                    <div className="dropzone-inner">
                      <Upload size={24} style={{ color: 'var(--accent)' }} />
                      <div>Click or drag {imageCategory === 'logo' ? 'Company Logo / Symbol' : 'an image'} here</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>PNG, SVG, JPG, WEBP — max 50MB</div>
                    </div>
                  )}
                </label>
              </div>
            </div>
          )}

          {/* Source 2: Pick Existing Uploaded Image */}
          {sourceType === 'existing' && imageFiles.length > 0 && (
            <div className="form-group">
              <label className="form-label">Select File</label>
              <div className="image-grid">
                {imageFiles.map((f, i) => (
                  <div
                    key={i}
                    className={`image-grid-item ${existingFilename === f.filename ? 'selected' : ''}`}
                    onClick={() => setExistingFilename(f.filename)}
                  >
                    <span style={{ fontSize: 24 }}>{imageCategory === 'logo' ? '🏢' : '🖼️'}</span>
                    <span className="image-grid-name">{f.filename}</span>
                    {existingFilename === f.filename && (
                      <div className="image-check-badge"><Check size={12} /></div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Placement Target */}
          <div className="form-group">
            <label className="form-label">Placement Location</label>
            <div className="placement-options">
              {imageCategory === 'logo' && (
                <label className={`placement-card ${placementTarget === 'header_logo' ? 'selected' : ''}`}>
                  <input
                    type="radio"
                    name="placementTarget"
                    value="header_logo"
                    checked={placementTarget === 'header_logo'}
                    onChange={() => setPlacementTarget('header_logo')}
                  />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 12 }}>📌 Document Header & Cover Title</div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                      Places logo prominently at top of document pages and cover
                    </div>
                  </div>
                </label>
              )}
              <label className={`placement-card ${placementTarget === 'section' ? 'selected' : ''}`}>
                <input
                  type="radio"
                  name="placementTarget"
                  value="section"
                  checked={placementTarget === 'section'}
                  onChange={() => setPlacementTarget('section')}
                />
                <div>
                  <div style={{ fontWeight: 600, fontSize: 12 }}>📌 Specific Document Section / Page</div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                    Inserts symbol/logo anywhere inside selected section
                  </div>
                </div>
              </label>
            </div>
          </div>

          {/* Target Section Dropdown (if placement is section) */}
          {placementTarget === 'section' && (
            <div className="form-group">
              <label className="form-label">
                Target Section
                {loadingSections && <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--accent)' }}>Loading sections…</span>}
              </label>
              <select
                className="form-select"
                value={targetSection}
                onChange={(e) => setTargetSection(e.target.value)}
              >
                <option value="">First Section (Default)</option>
                {sections.map((sec, idx) => (
                  <option key={idx} value={sec}>
                    Section: {sec}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Caption (optional for images, hidden by default for logos) */}
          {imageCategory === 'image' && (
            <div className="form-group">
              <label className="form-label">Caption (Optional)</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g., Figure 1: System Architecture Diagram"
                value={caption}
                onChange={(e) => setCaption(e.target.value)}
              />
            </div>
          )}

          {/* Alignment & Width */}
          <div className="form-row">
            <div className="form-group" style={{ flex: 1 }}>
              <label className="form-label">Alignment</label>
              <div className="align-buttons">
                {['left', 'center', 'right'].map((a) => (
                  <button
                    key={a}
                    type="button"
                    className={`align-btn ${align === a ? 'active' : ''}`}
                    onClick={() => setAlign(a)}
                  >
                    {a.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            <div className="form-group" style={{ flex: 1 }}>
              <label className="form-label">Width: {widthInches} inches</label>
              <input
                type="range"
                min="0.5"
                max="6.5"
                step="0.25"
                value={widthInches}
                onChange={(e) => setWidthInches(parseFloat(e.target.value))}
                className="form-range"
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)' }}>
                <span>Symbol (1")</span>
                <span>Logo (2")</span>
                <span>Full (6.5")</span>
              </div>
            </div>
          </div>

          {/* Footer Actions */}
          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? (
                <>
                  <Loader2 size={14} className="spin" /> Inserting…
                </>
              ) : (
                `✨ Insert ${imageCategory === 'logo' ? 'Logo' : 'Image'}`
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
