import React, { useRef, useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { Send, Paperclip } from 'lucide-react'
import toast from 'react-hot-toast'
import { sendMessage } from '../api/client'

const SUGGESTIONS = [
  '🔬 Research Generative AI trends and create a report',
  '📊 Create a 12-slide presentation on Machine Learning',
  '📄 Generate a business proposal document',
  '✏️ Add an executive summary to the document',
  '🔄 Make the presentation more concise',
  '📈 Add a competitive analysis section',
]

function ThinkingIndicator() {
  return (
    <div className="message-row">
      <div className="message-avatar assistant-avatar">🤖</div>
      <div className="thinking-indicator">
        <div className="thinking-dots">
          <div className="thinking-dot" />
          <div className="thinking-dot" />
          <div className="thinking-dot" />
        </div>
        <span>Agents working…</span>
      </div>
    </div>
  )
}

function Message({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`message-row ${isUser ? 'user' : ''}`}>
      <div className={`message-avatar ${isUser ? 'user-avatar' : 'assistant-avatar'}`}>
        {isUser ? '👤' : '🤖'}
      </div>
      <div className={`message-bubble ${isUser ? 'user' : 'assistant'}`}>
        {isUser ? (
          <span>{msg.content}</span>
        ) : (
          <ReactMarkdown>{msg.content}</ReactMarkdown>
        )}
      </div>
    </div>
  )
}

export default function ChatPanel({
  sessionId,
  uploadedFileIds,
  onChatResponse,
}) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSend = async (text = input.trim()) => {
    if (!text || loading) return

    const userMsg = { role: 'user', content: text, timestamp: new Date().toISOString() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const result = await sendMessage(text, sessionId, uploadedFileIds)
      const assistantMsg = {
        role: 'assistant',
        content: result.response,
        timestamp: new Date().toISOString(),
      }
      setMessages(prev => [...prev, assistantMsg])
      onChatResponse(result)
    } catch (err) {
      const errMsg = {
        role: 'assistant',
        content: `❌ Error: ${err.response?.data?.detail || err.message || 'Something went wrong'}`,
        timestamp: new Date().toISOString(),
      }
      setMessages(prev => [...prev, errMsg])
      toast.error('Request failed')
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleTextareaChange = (e) => {
    setInput(e.target.value)
    const ta = textareaRef.current
    if (ta) {
      ta.style.height = 'auto'
      ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
    }
  }

  return (
    <div className="chat-panel">
      <div className="messages-container">
        {messages.length === 0 ? (
          <div className="welcome-screen">
            <div className="welcome-orb">🤖</div>
            <h1 className="welcome-title">AgentDoc AI Studio</h1>
            <p className="welcome-subtitle">
              Upload templates, ask questions, and let multi-agent AI generate
              professional documents and presentations for you.
            </p>
            <div className="suggestion-chips">
              {SUGGESTIONS.map((s, i) => (
                <button key={i} className="chip" onClick={() => handleSend(s.replace(/^[^\s]+\s/, '').trim())}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, i) => <Message key={i} msg={msg} />)
        )}
        {loading && <ThinkingIndicator />}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-area">
        <div className="chat-input-row">
          <textarea
            ref={textareaRef}
            className="chat-textarea"
            value={input}
            onChange={handleTextareaChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask me to research, generate documents, presentations, or edit existing ones…"
            rows={1}
            disabled={loading}
          />
          <button
            className="send-btn"
            onClick={() => handleSend()}
            disabled={!input.trim() || loading}
          >
            <Send size={18} />
          </button>
        </div>
        <div className="input-hint">Press Enter to send · Shift+Enter for new line</div>
      </div>
    </div>
  )
}
