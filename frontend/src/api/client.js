import axios from 'axios'

const API = axios.create({
  baseURL: '/api',
  timeout: 900000, // 15 min timeout for generation
})

export const uploadFiles = async (files) => {
  const formData = new FormData()
  files.forEach(f => formData.append('files', f))
  const res = await API.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export const sendMessage = async (message, sessionId, fileIds = []) => {
  const res = await API.post('/chat', {
    message,
    session_id: sessionId,
    file_ids: fileIds,
  })
  return res.data
}

export const getVersions = async (artifactId) => {
  const res = await API.get(`/versions/${artifactId}`)
  return res.data
}

export const listArtifacts = async () => {
  const res = await API.get('/artifacts')
  return res.data
}

export const getKnowledgeStats = async () => {
  const res = await API.get('/knowledge')
  return res.data
}

export const getHealth = async () => {
  const res = await API.get('/health')
  return res.data
}

export const getSession = async (sessionId) => {
  const res = await API.get(`/session/${sessionId}`)
  return res.data
}

export const clearSession = async (sessionId) => {
  const res = await API.delete(`/session/${sessionId}`)
  return res.data
}

export const getDocumentSections = async (artifactId) => {
  const res = await API.get(`/document/${artifactId}/sections`)
  return res.data
}

export const insertImageToDoc = async (formData) => {
  const res = await API.post('/document/insert-image', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export const downloadFile = (filename) => {
  window.open(`/api/download/${filename}`, '_blank')
}
