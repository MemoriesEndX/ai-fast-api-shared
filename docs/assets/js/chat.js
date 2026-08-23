/**
 * Simple AI Chat UI Client - Phase 20.5
 * Communicates strictly with POST /api/v1/chat
 * No hardcoded API keys, in-memory state only, full XSS sanitization.
 */
(function () {
  'use strict';

  // In-memory conversation state (strictly ephemeral session only)
  let currentConversationId = null;
  let inMemoryApiKey = '';
  let selectedApp = 'owl';
  let isRequestPending = false;
  let lastUserMessage = '';

  // DOM Elements
  let chatMessagesEl;
  let emptyStateEl;
  let messageInputEl;
  let sendBtnEl;
  let healthBadgeEl;
  let healthDotEl;
  let healthTextEl;
  let apiKeyModalEl;
  let apiKeyInputEl;
  let apiKeyBtnEl;

  // HTML Sanitization to prevent XSS / Script Injection
  function sanitizeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Safe Minimal Markdown Parser
  function renderSafeMarkdown(text) {
    if (!text) return '';

    // Step 1: Escape untrusted HTML characters
    let escaped = sanitizeHtml(text);

    // Step 2: Extract & protect fenced code blocks
    const codeBlocks = [];
    escaped = escaped.replace(/```([a-zA-Z0-9_\-\+]*)\n([\s\S]*?)```/g, (match, lang, code) => {
      const id = codeBlocks.length;
      const cleanLang = lang ? lang.trim() : 'text';
      codeBlocks.push({ lang: cleanLang, code: code.trim() });
      return `@@CODE_BLOCK_${id}@@`;
    });

    // Step 3: Inline code (`code`)
    escaped = escaped.replace(/`([^`\n]+)`/g, '<code class="inline-code">$1</code>');

    // Step 4: Blockquotes
    escaped = escaped.replace(/(?:^|\n)&gt;\s?(.*?)(?=\n|$)/g, '\n<blockquote>$1</blockquote>');

    // Step 5: Bold (**text** or __text__)
    escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    escaped = escaped.replace(/__(.*?)__/g, '<strong>$1</strong>');

    // Step 6: Italic (*text* or _text_)
    escaped = escaped.replace(/(^|[^\*])\*([^\*\n]+)\*([^\*]|$)/g, '$1<em>$2</em>$3');
    escaped = escaped.replace(/(^|[^_])_([^_\n]+)_([^_]|$)/g, '$1<em>$2</em>$3');

    // Step 7: Lists (unordered - and *)
    escaped = escaped.replace(/(?:^|\n)[-\*]\s+(.+)/g, '\n<li>$1</li>');
    escaped = escaped.replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>');
    // Fix nested UL issues from regex
    escaped = escaped.replace(/<\/ul>\s*<ul>/g, '');

    // Step 8: Paragraphs & Linebreaks
    const paragraphs = escaped.split(/\n{2,}/);
    let htmlResult = paragraphs
      .map((p) => {
        p = p.trim();
        if (!p) return '';
        if (p.startsWith('<ul>') || p.startsWith('<blockquote>') || p.startsWith('@@CODE_BLOCK_')) {
          return p.replace(/\n/g, '<br/>');
        }
        return `<p>${p.replace(/\n/g, '<br/>')}</p>`;
      })
      .filter(Boolean)
      .join('');

    // Step 9: Restore Code Blocks
    codeBlocks.forEach((block, idx) => {
      const rawCode = block.code;
      const blockHtml = `
        <div class="chat-code-block">
          <div class="code-header">
            <span class="code-lang">${block.lang}</span>
            <button class="code-copy-btn" onclick="window.ChatUI.copySnippet(this, decodeURIComponent('${encodeURIComponent(rawCode)}'))">Copy</button>
          </div>
          <pre><code>${rawCode}</code></pre>
        </div>
      `;
      htmlResult = htmlResult.replace(`@@CODE_BLOCK_${idx}@@`, blockHtml);
    });

    return htmlResult;
  }

  // Live Health Check
  async function checkHealth() {
    try {
      const res = await fetch('/health', { method: 'GET' });
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'ok') {
          healthBadgeEl.className = 'health-badge online';
          healthTextEl.textContent = 'AI Service Online';
          return;
        }
      }
      healthBadgeEl.className = 'health-badge offline';
      healthTextEl.textContent = 'AI Service Offline';
    } catch (e) {
      healthBadgeEl.className = 'health-badge offline';
      healthTextEl.textContent = 'AI Service Offline';
    }
  }

  // Auto-scroll chat area to bottom
  function scrollToBottom() {
    const mainEl = document.getElementById('chat-main-area');
    if (mainEl) {
      mainEl.scrollTop = mainEl.scrollHeight;
    }
  }

  // Adjust textarea height dynamically
  function adjustTextareaHeight() {
    if (!messageInputEl) return;
    messageInputEl.style.height = 'auto';
    messageInputEl.style.height = Math.min(messageInputEl.scrollHeight, 150) + 'px';
  }

  // Render User Message
  function appendUserMessage(text) {
    if (emptyStateEl) emptyStateEl.style.display = 'none';

    const row = document.createElement('div');
    row.className = 'message-row user-row';
    row.innerHTML = `
      <div class="message-content-wrapper">
        <div class="message-bubble user-bubble">${sanitizeHtml(text)}</div>
      </div>
    `;
    chatMessagesEl.appendChild(row);
    scrollToBottom();
  }

  // Show Loading Bubble
  function showLoadingIndicator() {
    const loadingRow = document.createElement('div');
    loadingRow.id = 'ai-loading-indicator';
    loadingRow.className = 'message-row ai-row';
    loadingRow.innerHTML = `
      <div class="ai-avatar">AI</div>
      <div class="message-content-wrapper">
        <div class="loading-bubble">
          <div class="loading-dots">
            <span class="loading-dot"></span>
            <span class="loading-dot"></span>
            <span class="loading-dot"></span>
          </div>
          <span class="loading-text">AI is thinking...</span>
        </div>
      </div>
    `;
    chatMessagesEl.appendChild(loadingRow);
    scrollToBottom();
  }

  // Remove Loading Bubble
  function removeLoadingIndicator() {
    const el = document.getElementById('ai-loading-indicator');
    if (el) el.remove();
  }

  // Render AI Response Message
  function appendAIMessage(data, rawAnswer, meta) {
    if (emptyStateEl) emptyStateEl.style.display = 'none';

    const row = document.createElement('div');
    row.className = 'message-row ai-row';

    const safeAnswerHtml = renderSafeMarkdown(rawAnswer);

    // Sources rendering if present
    let sourcesHtml = '';
    if (Array.isArray(data.sources) && data.sources.length > 0) {
      const sourceItems = data.sources
        .map((s) => {
          const type = sanitizeHtml(s.type || s.source_type || 'doc');
          const title = sanitizeHtml(s.title || s.filename || 'Source Document');
          const score = typeof s.score === 'number' ? `(${(s.score * 100).toFixed(0)}%)` : '';
          return `
            <div class="source-item">
              <span class="source-type-tag">${type}</span>
              <span style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${title}</span>
              <span style="color: var(--text-muted); font-size: 0.7rem;">${score}</span>
            </div>
          `;
        })
        .join('');

      sourcesHtml = `
        <details class="sources-card" style="margin-top: 0.75rem;">
          <summary class="sources-header">
            <span>Grounding Sources (${data.sources.length})</span>
          </summary>
          <div class="sources-list">${sourceItems}</div>
        </details>
      `;
    }

    // Debug Info Collapsible
    const latency = data.latency_ms ? `${data.latency_ms.toFixed(1)}ms` : meta.clientLatency ? `${meta.clientLatency}ms` : 'N/A';
    const reqId = meta.requestId || 'unknown';
    const convId = data.conversation_id || currentConversationId || 'None';
    const model = data.model || 'Qwen2.5 0.5B';
    const provider = data.provider || 'llama_cpp';
    const toolsUsed = Array.isArray(data.tools_used) && data.tools_used.length > 0 ? data.tools_used.join(', ') : 'None';

    const debugHtml = `
      <details class="debug-details">
        <summary>Debug Info</summary>
        <div class="debug-content">
          <div><strong>Status:</strong> 200 OK</div>
          <div><strong>Latency:</strong> ${sanitizeHtml(latency)}</div>
          <div><strong>Request ID:</strong> ${sanitizeHtml(reqId)}</div>
          <div><strong>Conversation ID:</strong> ${sanitizeHtml(convId)}</div>
          <div><strong>Model / Provider:</strong> ${sanitizeHtml(model)} (${sanitizeHtml(provider)})</div>
          <div><strong>Tools Used:</strong> ${sanitizeHtml(toolsUsed)}</div>
        </div>
      </details>
    `;

    // Encoded plain text answer for copy button
    const encodedRaw = encodeURIComponent(rawAnswer);

    row.innerHTML = `
      <div class="ai-avatar">AI</div>
      <div class="message-content-wrapper">
        <div class="message-bubble ai-bubble">
          ${safeAnswerHtml}
          ${sourcesHtml}
        </div>
        <div class="message-actions">
          <button class="msg-action-btn" onclick="window.ChatUI.copyMessage(this, decodeURIComponent('${encodedRaw}'))">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
            </svg>
            <span>Copy</span>
          </button>
        </div>
        ${debugHtml}
      </div>
    `;

    chatMessagesEl.appendChild(row);
    scrollToBottom();
  }

  // Render Error Message Bubble
  function appendErrorMessage(errorText, canRetry = true, meta = {}) {
    if (emptyStateEl) emptyStateEl.style.display = 'none';

    const row = document.createElement('div');
    row.className = 'message-row ai-row error-message-row';

    const safeError = sanitizeHtml(errorText);
    const retryBtn = canRetry
      ? `<button class="error-btn" onclick="window.ChatUI.retryLastMessage(this)">Retry</button>`
      : '';

    const reqId = meta.requestId ? `<div><strong>Request ID:</strong> ${sanitizeHtml(meta.requestId)}</div>` : '';
    const status = meta.status ? `<div><strong>Status:</strong> ${sanitizeHtml(meta.status)}</div>` : '';

    const debugHtml = (reqId || status)
      ? `
        <details class="debug-details" style="margin-top: 0.4rem;">
          <summary>Error Details</summary>
          <div class="debug-content">
            ${status}
            ${reqId}
          </div>
        </details>
      ` : '';

    row.innerHTML = `
      <div class="ai-avatar" style="background: #ef4444;">!</div>
      <div class="message-content-wrapper">
        <div class="error-bubble">
          <div class="error-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <span>Unable to get response</span>
          </div>
          <div>${safeError}</div>
          ${retryBtn}
        </div>
        ${debugHtml}
      </div>
    `;

    chatMessagesEl.appendChild(row);
    scrollToBottom();
  }

  // Send Message Logic
  async function sendMessage(text) {
    const cleanText = (text || '').trim();
    if (!cleanText || isRequestPending) return;

    lastUserMessage = cleanText;
    isRequestPending = true;

    // Reset input
    if (messageInputEl) {
      messageInputEl.value = '';
      adjustTextareaHeight();
      messageInputEl.disabled = true;
    }
    if (sendBtnEl) sendBtnEl.disabled = true;

    appendUserMessage(cleanText);
    showLoadingIndicator();

    const startTime = performance.now();

    // Prepare Request Body according to OpenAPI ChatRequest schema
    const payload = {
      application: selectedApp,
      user_id: 1,
      message: cleanText,
    };

    if (currentConversationId) {
      payload.conversation_id = currentConversationId;
    }

    const headers = {
      'Content-Type': 'application/json',
    };

    if (inMemoryApiKey) {
      headers['X-API-Key'] = inMemoryApiKey;
      headers['Authorization'] = `Bearer ${inMemoryApiKey}`;
    }

    try {
      const response = await fetch('/api/v1/chat', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload),
      });

      const elapsed = Math.round(performance.now() - startTime);
      const requestId = response.headers.get('x-request-id') || '';

      removeLoadingIndicator();

      if (response.ok) {
        const data = await response.json();

        // Update active conversation session ID
        if (data.conversation_id) {
          currentConversationId = data.conversation_id;
        }

        const answer = data.answer || data.message || '';
        appendAIMessage(data, answer, {
          requestId: requestId,
          clientLatency: elapsed,
        });
      } else {
        // Structured error handling
        let errorMessage = 'Unable to get response.';
        try {
          const errData = await response.json();
          if (errData && errData.error && errData.error.message) {
            errorMessage = errData.error.message;
          } else if (errData && errData.detail) {
            errorMessage = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
          }
        } catch (e) {
          errorMessage = `HTTP ${response.status} ${response.statusText}`;
        }

        appendErrorMessage(errorMessage, true, {
          status: `${response.status} ${response.statusText}`,
          requestId: requestId,
        });
      }
    } catch (networkError) {
      removeLoadingIndicator();
      appendErrorMessage('AI Service unavailable. Please check your network connection or server status.', true, {
        status: 'Network Failure',
      });
    } finally {
      isRequestPending = false;
      if (messageInputEl) {
        messageInputEl.disabled = false;
        messageInputEl.focus();
      }
      if (sendBtnEl) sendBtnEl.disabled = false;
    }
  }

  // Clear / New Chat
  function newChat() {
    currentConversationId = null;
    lastUserMessage = '';
    if (chatMessagesEl) {
      chatMessagesEl.innerHTML = '';
    }
    if (emptyStateEl) {
      emptyStateEl.style.display = 'flex';
    }
    if (messageInputEl) {
      messageInputEl.value = '';
      adjustTextareaHeight();
      messageInputEl.focus();
    }
  }

  // Retry Last Message
  function retryLastMessage(btnEl) {
    if (isRequestPending || !lastUserMessage) return;
    const errorRow = btnEl.closest('.error-message-row');
    if (errorRow) errorRow.remove();
    sendMessage(lastUserMessage);
  }

  // Copy Plain Text Response
  function copyMessage(btn, text) {
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
      const span = btn.querySelector('span');
      if (span) {
        const origText = span.textContent;
        span.textContent = 'Copied ✓';
        btn.style.color = '#10b981';
        setTimeout(() => {
          span.textContent = origText;
          btn.style.color = '';
        }, 2000);
      }
    });
  }

  // Copy Code Snippet
  function copySnippet(btn, code) {
    if (!code) return;
    navigator.clipboard.writeText(code).then(() => {
      const orig = btn.textContent;
      btn.textContent = 'Copied ✓';
      setTimeout(() => {
        btn.textContent = orig;
      }, 2000);
    });
  }

  // In-Memory API Key Management
  function openApiKeyModal() {
    if (apiKeyModalEl) {
      apiKeyInputEl.value = inMemoryApiKey || '';
      apiKeyModalEl.classList.add('active');
      apiKeyInputEl.focus();
    }
  }

  function closeApiKeyModal() {
    if (apiKeyModalEl) {
      apiKeyModalEl.classList.remove('active');
    }
  }

  function saveApiKey() {
    if (apiKeyInputEl) {
      inMemoryApiKey = apiKeyInputEl.value.trim();
      updateApiKeyButtonState();
      closeApiKeyModal();
    }
  }

  function clearApiKey() {
    inMemoryApiKey = '';
    if (apiKeyInputEl) apiKeyInputEl.value = '';
    updateApiKeyButtonState();
    closeApiKeyModal();
  }

  function updateApiKeyButtonState() {
    if (apiKeyBtnEl) {
      if (inMemoryApiKey) {
        apiKeyBtnEl.classList.add('chat-btn-primary');
        apiKeyBtnEl.setAttribute('title', 'In-memory API Key is active');
      } else {
        apiKeyBtnEl.classList.remove('chat-btn-primary');
        apiKeyBtnEl.setAttribute('title', 'Set in-memory API Key (Optional)');
      }
    }
  }

  // Initialize UI Event Listeners
  function init() {
    chatMessagesEl = document.getElementById('chat-messages-container');
    emptyStateEl = document.getElementById('chat-empty-state');
    messageInputEl = document.getElementById('chat-message-input');
    sendBtnEl = document.getElementById('chat-send-button');
    healthBadgeEl = document.getElementById('chat-health-badge');
    healthDotEl = document.getElementById('chat-health-dot');
    healthTextEl = document.getElementById('chat-health-text');
    apiKeyModalEl = document.getElementById('api-key-modal');
    apiKeyInputEl = document.getElementById('api-key-input');
    apiKeyBtnEl = document.getElementById('api-key-btn');

    // App tenant selection listener
    const appSelectEl = document.getElementById('chat-app-select');
    if (appSelectEl) {
      appSelectEl.addEventListener('change', (e) => {
        selectedApp = e.target.value;
      });
    }

    // Textarea input listeners
    if (messageInputEl) {
      messageInputEl.addEventListener('input', adjustTextareaHeight);
      messageInputEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          sendMessage(messageInputEl.value);
        }
      });
    }

    // Send button click
    if (sendBtnEl) {
      sendBtnEl.addEventListener('click', () => {
        if (messageInputEl) {
          sendMessage(messageInputEl.value);
        }
      });
    }

    // Live Health check
    checkHealth();
    setInterval(checkHealth, 30000);

    // Dark/Light Theme Setup (reusing DocTheme if present)
    const themeToggleBtn = document.getElementById('chat-theme-toggle');
    if (themeToggleBtn && window.DocTheme) {
      themeToggleBtn.addEventListener('click', () => {
        window.DocTheme.toggleTheme();
      });
    }
  }

  // Public Chat UI Module Object
  window.ChatUI = {
    init,
    sendMessage,
    newChat,
    retryLastMessage,
    copyMessage,
    copySnippet,
    openApiKeyModal,
    closeApiKeyModal,
    saveApiKey,
    clearApiKey,
    useSuggestion: function (text) {
      sendMessage(text);
    },
  };

  // Run on DOM Content Loaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
