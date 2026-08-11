/* API Playground / Try It Module - Secure In-Memory Execution */
(function () {
  // In-memory token storage (never written to localStorage or logged!)
  let inMemoryToken = 'dev-shared-ai-key-change-in-production';

  function togglePlayground(btn, method, path, sampleBodyJson) {
    const card = btn.closest('.endpoint-card');
    const container = card.querySelector('.playground-container');
    if (!container) return;

    if (container.style.display === 'block') {
      container.style.display = 'none';
      return;
    }

    let parsedBody = {};
    try {
      if (sampleBodyJson) parsedBody = JSON.parse(sampleBodyJson);
    } catch (e) {}

    const prettyBody = JSON.stringify(parsedBody, null, 2);

    container.innerHTML = `
      <div class="playground-panel">
        <form class="playground-form" onsubmit="event.preventDefault(); window.DocPlayground.sendRequest(this, '${method}', '${path}');">
          <div class="form-group">
            <label class="form-label">X-API-Key Authorization Header</label>
            <input type="password" class="form-input pg-auth-token" value="${inMemoryToken}" placeholder="Enter API Key" autocomplete="off" onchange="window.DocPlayground.updateToken(this.value)" />
            <span style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem; display: block;">Token held in memory for this session only.</span>
          </div>

          <div class="form-group pg-body-group">
            <label class="form-label">Request Body (JSON)</label>
            <textarea class="form-textarea pg-json-body" rows="6">${prettyBody}</textarea>
          </div>

          <div style="display: flex; gap: 0.75rem; align-items: center; margin-top: 1rem;">
            <button type="submit" class="btn-primary pg-send-btn">
              <span>Send Request</span>
            </button>
            <button type="button" class="btn-secondary" onclick="window.DocPlayground.resetForm(this, '${escapeHtml(prettyBody)}')">
              <span>Reset</span>
            </button>
          </div>
        </form>

        <div class="pg-response-wrapper" style="display: none; margin-top: 1.5rem; border-top: 1px solid var(--border-color); padding-top: 1rem;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;">
            <div style="display: flex; align-items: center; gap: 0.75rem;">
              <span class="pg-status-badge" style="font-family: var(--font-mono); font-size: 0.8rem; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 4px;"></span>
              <span class="pg-latency-badge" style="font-size: 0.8rem; color: var(--text-muted);"></span>
            </div>
            <button class="copy-btn" onclick="window.DocPlayground.copyResponse(this)">Copy Response</button>
          </div>
          <div class="code-block-container">
            <pre><code class="pg-response-json"></code></pre>
          </div>
        </div>
      </div>
    `;

    container.style.display = 'block';
  }

  function updateToken(val) {
    inMemoryToken = val;
  }

  async function sendRequest(form, method, path) {
    const tokenInput = form.querySelector('.pg-auth-token');
    const bodyInput = form.querySelector('.pg-json-body');
    const sendBtn = form.querySelector('.pg-send-btn');
    const container = form.closest('.playground-panel');
    const responseWrapper = container.querySelector('.pg-response-wrapper');
    const statusBadge = container.querySelector('.pg-status-badge');
    const latencyBadge = container.querySelector('.pg-latency-badge');
    const responseCode = container.querySelector('.pg-response-json');

    const apiKey = tokenInput ? tokenInput.value : inMemoryToken;
    let payload = null;

    if (method.toUpperCase() !== 'GET' && method.toUpperCase() !== 'HEAD' && bodyInput) {
      try {
        payload = JSON.parse(bodyInput.value);
      } catch (err) {
        alert('Invalid JSON in request body: ' + err.message);
        return;
      }
    }

    sendBtn.disabled = true;
    sendBtn.innerText = 'Sending...';

    const startTime = performance.now();
    try {
      const headers = {
        'Content-Type': 'application/json',
      };
      if (apiKey) {
        headers['X-API-Key'] = apiKey;
      }

      const options = {
        method: method.toUpperCase(),
        headers: headers,
      };
      if (payload) {
        options.body = JSON.stringify(payload);
      }

      const res = await fetch(path, options);
      const endTime = performance.now();
      const latency = Math.round(endTime - startTime);

      let resData;
      const contentType = res.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        resData = await res.json();
      } else {
        resData = await res.text();
      }

      // Render response
      responseWrapper.style.display = 'block';
      statusBadge.innerText = `${res.status} ${res.statusText || ''}`;
      if (res.ok) {
        statusBadge.style.background = 'var(--badge-get-bg)';
        statusBadge.style.color = 'var(--badge-get-text)';
      } else {
        statusBadge.style.background = 'var(--badge-delete-bg)';
        statusBadge.style.color = 'var(--badge-delete-text)';
      }

      latencyBadge.innerText = `${latency}ms`;
      responseCode.textContent = typeof resData === 'object' ? JSON.stringify(resData, null, 2) : resData;
    } catch (err) {
      const endTime = performance.now();
      const latency = Math.round(endTime - startTime);
      responseWrapper.style.display = 'block';
      statusBadge.innerText = `Network Error`;
      statusBadge.style.background = 'var(--badge-delete-bg)';
      statusBadge.style.color = 'var(--badge-delete-text)';
      latencyBadge.innerText = `${latency}ms`;
      responseCode.textContent = JSON.stringify({ error: err.message }, null, 2);
    } finally {
      sendBtn.disabled = false;
      sendBtn.innerText = 'Send Request';
    }
  }

  function resetForm(btn, defaultBody) {
    const panel = btn.closest('.playground-panel');
    const bodyInput = panel.querySelector('.pg-json-body');
    const responseWrapper = panel.querySelector('.pg-response-wrapper');
    if (bodyInput && defaultBody) bodyInput.value = defaultBody;
    if (responseWrapper) responseWrapper.style.display = 'none';
  }

  function copyResponse(btn) {
    const panel = btn.closest('.playground-panel');
    const code = panel.querySelector('.pg-response-json');
    if (!code) return;
    navigator.clipboard.writeText(code.textContent).then(() => {
      const origText = btn.innerText;
      btn.innerText = 'Copied ✓';
      setTimeout(() => { btn.innerText = origText; }, 2000);
    });
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  window.DocPlayground = {
    togglePlayground,
    sendRequest,
    resetForm,
    copyResponse,
    updateToken,
  };
})();
