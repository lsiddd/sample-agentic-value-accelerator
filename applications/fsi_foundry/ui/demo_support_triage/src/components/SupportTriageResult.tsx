import { useState } from 'react';

interface SupportTriageResultProps {
  response: any;
  onNewRequest: () => void;
}

const CATEGORY_COLORS: Record<string, string> = {
  technical_issue: '#3b82f6', // Blue
  billing_inquiry: '#a855f7', // Purple
  feature_request: '#22c55e', // Green
  complaint: '#ef4444', // Red
  general_question: '#6b7280', // Gray
  account_access: '#f97316', // Orange
  product_info: '#06b6d4', // Cyan
  other: '#64748b', // Slate
};

const URGENCY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  low: { bg: '#22c55e20', text: '#22c55e', border: '#22c55e40' },
  medium: { bg: '#eab30820', text: '#eab308', border: '#eab30840' },
  high: { bg: '#f9731620', text: '#f97316', border: '#f9731640' },
  urgent: { bg: '#ef444420', text: '#ef4444', border: '#ef444440' },
};

const CATEGORY_LABELS: Record<string, string> = {
  technical_issue: 'Technical Issue',
  billing_inquiry: 'Billing Inquiry',
  feature_request: 'Feature Request',
  complaint: 'Complaint',
  general_question: 'General Question',
  account_access: 'Account Access',
  product_info: 'Product Info',
  other: 'Other',
};

export default function SupportTriageResult({ response, onNewRequest }: SupportTriageResultProps) {
  const [showReasoning, setShowReasoning] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [suggestedResponse, setSuggestedResponse] = useState(response.suggested_response || '');
  const [editedResponse, setEditedResponse] = useState(response.suggested_response || '');

  const category = response.category || 'other';
  const urgency = response.urgency || 'low';
  const confidence = response.confidence ?? 0;
  const reasoning = response.reasoning || '';

  const categoryColor = CATEGORY_COLORS[category] || CATEGORY_COLORS.other;
  const urgencyStyle = URGENCY_COLORS[urgency] || URGENCY_COLORS.low;

  const handleApprove = () => {
    alert('Response approved! (Demo action - no actual message sent)');
    onNewRequest();
  };

  const handleEdit = () => {
    setIsEditing(true);
  };

  const handleSaveEdit = () => {
    setSuggestedResponse(editedResponse);
    setIsEditing(false);
    alert('Response updated! (Demo action)');
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditedResponse(suggestedResponse);
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="rounded-xl border p-6" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-400" style={{ boxShadow: '0 0 6px var(--success)' }} />
            <span className="text-xs font-semibold uppercase tracking-wider text-green-400">Complete</span>
          </div>
          <div className="flex items-center gap-3">
            {/* Confidence Score */}
            <div className="flex items-center gap-2">
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Confidence</span>
              <div className="w-24 h-2 rounded-full bg-slate-700 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.min(confidence * 100, 100)}%`,
                    background: confidence >= 0.8 ? '#22c55e' : confidence >= 0.6 ? '#eab308' : '#f97316',
                  }}
                />
              </div>
              <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                {Math.round(confidence * 100)}%
              </span>
            </div>
          </div>
        </div>

        {/* Category and Urgency Badges */}
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <div
            className="px-3 py-1.5 rounded-lg text-sm font-medium"
            style={{
              background: `${categoryColor}20`,
              color: categoryColor,
              border: `1px solid ${categoryColor}40`,
            }}
          >
            {CATEGORY_LABELS[category] || category}
          </div>
          <div
            className="px-3 py-1.5 rounded-lg text-sm font-medium flex items-center gap-1.5"
            style={{
              background: urgencyStyle.bg,
              color: urgencyStyle.text,
              border: `1px solid ${urgencyStyle.border}`,
            }}
          >
            <span className="w-2 h-2 rounded-full" style={{ background: urgencyStyle.text }} />
            {urgency.charAt(0).toUpperCase() + urgency.slice(1)} Urgency
          </div>
        </div>

        {/* Summary */}
        {response.summary && (
          <div className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            {response.summary}
          </div>
        )}
      </div>

      {/* Suggested Response Card */}
      <div className="rounded-xl border p-6" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
            Suggested Response
          </h3>
          {!isEditing && (
            <div className="flex gap-2">
              <button
                onClick={handleApprove}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-green-500/10 text-green-400 border border-green-500/20 hover:bg-green-500/20 transition-colors"
              >
                Approve
              </button>
              <button
                onClick={handleEdit}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-sky-500/10 text-sky-400 border border-sky-500/20 hover:bg-sky-500/20 transition-colors"
              >
                Edit
              </button>
            </div>
          )}
        </div>

        {isEditing ? (
          <div className="space-y-3">
            <textarea
              value={editedResponse}
              onChange={(e) => setEditedResponse(e.target.value)}
              className="w-full px-4 py-3 rounded-lg text-sm bg-slate-900 border border-slate-700 text-white placeholder-slate-500 focus:border-sky-500 focus:outline-none min-h-[150px] resize-y"
              rows={6}
            />
            <div className="flex gap-2">
              <button
                onClick={handleSaveEdit}
                className="px-4 py-2 rounded-lg text-xs font-medium bg-sky-500 hover:bg-sky-400 text-white transition-colors"
              >
                Save Changes
              </button>
              <button
                onClick={handleCancelEdit}
                className="px-4 py-2 rounded-lg text-xs font-medium border border-slate-600 text-slate-300 hover:border-slate-400 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="p-4 rounded-lg bg-slate-900/50 border border-slate-700">
            <p className="text-sm leading-relaxed whitespace-pre-line" style={{ color: 'var(--text-secondary)' }}>
              {suggestedResponse || 'No response generated.'}
            </p>
          </div>
        )}
      </div>

      {/* Reasoning Section */}
      {reasoning && (
        <details
          className="rounded-xl border"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
          open={showReasoning}
          onToggle={(e) => setShowReasoning((e.target as HTMLDetailsElement).open)}
        >
          <summary className="px-6 py-4 cursor-pointer text-sm font-medium flex items-center justify-between" style={{ color: 'var(--text-secondary)' }}>
            <span>Classification Reasoning</span>
            <svg
              className={`w-4 h-4 transition-transform ${showReasoning ? 'rotate-180' : ''}`}
              style={{ color: 'var(--text-muted)' }}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </summary>
          <div className="px-6 pb-6">
            <div className="p-4 rounded-lg bg-slate-900/50 border border-slate-700">
              <p className="text-sm leading-relaxed whitespace-pre-line" style={{ color: 'var(--text-secondary)' }}>
                {reasoning}
              </p>
            </div>
          </div>
        </details>
      )}

      {/* Raw Response (for debugging) */}
      <details className="rounded-xl border" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
        <summary className="px-6 py-4 cursor-pointer text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
          Full Response (Debug)
        </summary>
        <div className="px-6 pb-6">
          <pre className="text-xs leading-relaxed overflow-auto max-h-96 p-4 rounded-lg bg-slate-900 border border-slate-800" style={{ color: 'var(--text-secondary)' }}>
            {JSON.stringify(response, null, 2)}
          </pre>
        </div>
      </details>

      {/* New Request Button */}
      <button
        onClick={onNewRequest}
        className="w-full px-4 py-2.5 rounded-lg font-semibold text-sm border border-slate-600 text-slate-300 hover:border-slate-400 hover:text-white transition-colors"
      >
        New Request
      </button>
    </div>
  );
}
