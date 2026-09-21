import React from 'react'

const STATUS_ICONS = {
  done: '✅',
  running: '⏳',
  error: '❌',
}

const AGENT_COLORS = {
  Supervisor: '#8b5cf6',
  DocumentAnalyzer: '#06b6d4',
  PPTAnalyzer: '#f59e0b',
  WebResearcher: '#10b981',
  RAGAgent: '#ec4899',
  DocGenerator: '#3b82f6',
  PPTGenerator: '#f97316',
  Validator: '#84cc16',
  Editor: '#a78bfa',
  ResponseComposer: '#8b5cf6',
}

export default function AgentTracePanel({ trace }) {
  if (!trace || trace.length === 0) {
    return (
      <div className="empty-state">
        <div style={{ fontSize: 28, marginBottom: 8 }}>🤖</div>
        <div>Agent trace will appear here</div>
        <div style={{ fontSize: 11, marginTop: 4 }}>Start a conversation to see the multi-agent workflow</div>
      </div>
    )
  }

  return (
    <div className="trace-container">
      {trace.map((step, i) => {
        const color = AGENT_COLORS[step.agent] || '#8b5cf6'
        const statusClass = step.status === 'done' ? 'done' : step.status === 'error' ? 'error' : 'running'

        return (
          <div
            key={i}
            className={`trace-item status-${step.status}`}
            style={{ animationDelay: `${i * 0.05}s` }}
          >
            <div style={{
              width: 28, height: 28,
              borderRadius: 8,
              background: `${color}22`,
              border: `1px solid ${color}55`,
              display: 'grid',
              placeItems: 'center',
              fontSize: 12,
              flexShrink: 0,
            }}>
              {step.status === 'running'
                ? <div className="trace-spinner" />
                : STATUS_ICONS[step.status] || '•'}
            </div>

            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="trace-agent-name" style={{ color }}>
                {step.agent}
              </div>
              <div className="trace-action">{step.action}</div>
              {step.detail && (
                <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                  {step.detail}
                </div>
              )}
            </div>

            <div>
              <span className={`trace-status-badge ${statusClass}`}>
                {step.status}
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
