/* OpenAPI Parser & Endpoint Renderer - Source of Truth: /openapi.json */
(function () {
  let openApiData = null;

  async function fetchOpenApiSpec() {
    if (openApiData) return openApiData;

    try {
      const response = await fetch('/openapi.json');
      if (!response.ok) throw new Error(`HTTP ${response.status} loading OpenAPI spec`);
      openApiData = await response.json();
      return openApiData;
    } catch (err) {
      console.error('Failed to load OpenAPI spec:', err);
      throw err;
    }
  }

  function resolveSchemaRef(ref, spec) {
    if (!ref || typeof ref !== 'string') return null;
    const parts = ref.replace('#/', '').split('/');
    let current = spec;
    for (const p of parts) {
      if (current && current[p]) {
        current = current[p];
      } else {
        return null;
      }
    }
    return current;
  }

  function generateSampleFromSchema(schema, spec) {
    if (!schema) return {};
    if (schema.$ref) {
      const resolved = resolveSchemaRef(schema.$ref, spec);
      return generateSampleFromSchema(resolved, spec);
    }
    if (schema.type === 'object' || schema.properties) {
      const obj = {};
      const props = schema.properties || {};
      for (const [key, prop] of Object.entries(props)) {
        if (prop.example !== undefined) {
          obj[key] = prop.example;
        } else if (prop.default !== undefined) {
          obj[key] = prop.default;
        } else if (prop.type === 'string') {
          if (prop.format === 'date-time') obj[key] = new Date().toISOString();
          else if (key.includes('message')) obj[key] = 'Hello AI Service';
          else if (key.includes('app')) obj[key] = 'owl';
          else if (key.includes('user')) obj[key] = 'user-123';
          else obj[key] = 'string';
        } else if (prop.type === 'integer' || prop.type === 'number') {
          obj[key] = prop.default || 1;
        } else if (prop.type === 'boolean') {
          obj[key] = prop.default || true;
        } else if (prop.type === 'array') {
          obj[key] = [generateSampleFromSchema(prop.items, spec)];
        } else if (prop.$ref) {
          obj[key] = generateSampleFromSchema(prop, spec);
        } else {
          obj[key] = null;
        }
      }
      return obj;
    }
    return {};
  }

  function generateCodeExamples(method, path, sampleBody, security) {
    const jsonStr = JSON.stringify(sampleBody, null, 2);
    const origin = window.location.origin;

    // cURL Example
    const curl = `curl -X ${method.toUpperCase()} "${origin}${path}" \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: dev-shared-ai-key-change-in-production" \\
  -d '${jsonStr}'`;

    // JavaScript Example
    const js = `fetch("${origin}${path}", {
  method: "${method.toUpperCase()}",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": "dev-shared-ai-key-change-in-production"
  },
  body: JSON.stringify(${jsonStr})
})
  .then(res => res.json())
  .then(data => console.log(data));`;

    // Python Example
    const python = `import requests

url = "${origin}${path}"
headers = {
    "Content-Type": "application/json",
    "X-API-Key": "dev-shared-ai-key-change-in-production"
}
payload = ${JSON.stringify(sampleBody, null, 4)}

response = requests.${method.toLowerCase()}(url, headers=headers, json=payload)
print(response.status_code, response.json())`;

    return { curl, js, python };
  }

  function renderEndpointCard(path, method, operation, spec) {
    const methodUpper = method.toUpperCase();
    const cardId = `ep-${methodUpper.toLowerCase()}-${path.replace(/[^a-zA-Z0-9]/g, '-')}`;

    // Extract request schema
    let requestSchema = null;
    let sampleBody = {};
    if (operation.requestBody && operation.requestBody.content) {
      const jsonContent = operation.requestBody.content['application/json'];
      if (jsonContent && jsonContent.schema) {
        requestSchema = jsonContent.schema;
        sampleBody = generateSampleFromSchema(requestSchema, spec);
      }
    }

    const snippets = generateCodeExamples(methodUpper, path, sampleBody);

    // Format Parameters
    let paramsHtml = '';
    if (operation.parameters && operation.parameters.length > 0) {
      paramsHtml += `
        <h4 style="font-size: 0.85rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.5rem;">Parameters</h4>
        <table class="docs-table">
          <thead>
            <tr><th>Name</th><th>In</th><th>Type</th><th>Required</th><th>Description</th></tr>
          </thead>
          <tbody>
      `;
      for (const p of operation.parameters) {
        paramsHtml += `
          <tr>
            <td><code>${p.name}</code></td>
            <td>${p.in}</td>
            <td>${(p.schema && p.schema.type) || 'string'}</td>
            <td>${p.required ? '<span style="color: var(--accent-primary);">Yes</span>' : 'No'}</td>
            <td>${p.description || '-'}</td>
          </tr>
        `;
      }
      paramsHtml += `</tbody></table>`;
    }

    // Format Responses
    let responsesHtml = `
      <h4 style="font-size: 0.85rem; text-transform: uppercase; color: var(--text-muted); margin-top: 1rem; margin-bottom: 0.5rem;">Responses</h4>
      <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
    `;
    if (operation.responses) {
      for (const code of Object.keys(operation.responses)) {
        const resp = operation.responses[code];
        const is2xx = code.startsWith('2');
        const badgeStyle = is2xx ? 'background: var(--badge-get-bg); color: var(--badge-get-text);' : 'background: var(--badge-delete-bg); color: var(--badge-delete-text);';
        responsesHtml += `
          <div style="padding: 0.4rem 0.8rem; border-radius: var(--radius-sm); border: 1px solid var(--border-color); font-size: 0.8rem; ${badgeStyle}">
            <strong>${code}</strong> - ${resp.description || ''}
          </div>
        `;
      }
    }
    responsesHtml += `</div>`;

    return `
      <div class="endpoint-card" id="${cardId}">
        <div class="endpoint-header">
          <span class="endpoint-method method-${method.toLowerCase()}">${methodUpper}</span>
          <span class="endpoint-path">${path}</span>
          <span class="endpoint-summary">${operation.summary || ''}</span>
        </div>
        <div class="endpoint-body">
          <p class="endpoint-description">${operation.description || operation.summary || 'No description provided.'}</p>
          
          <div class="endpoint-auth-badge">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
            <span>Auth Header: <strong>X-API-Key</strong></span>
          </div>

          ${paramsHtml}
          ${responsesHtml}

          <!-- Code Snippets Tabs -->
          <div style="margin-top: 1.5rem;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <h4 style="font-size: 0.85rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.5rem;">Request Examples</h4>
            </div>
            <div class="snippet-tabs">
              <button class="snippet-tab active" onclick="window.DocOpenApi.switchTab(this, 'curl')">cURL</button>
              <button class="snippet-tab" onclick="window.DocOpenApi.switchTab(this, 'js')">JavaScript</button>
              <button class="snippet-tab" onclick="window.DocOpenApi.switchTab(this, 'python')">Python</button>
            </div>
            <div class="code-block-container">
              <div class="code-header">
                <span class="code-lang-label">cURL</span>
                <button class="copy-btn" onclick="window.DocApp.copyCodeBlock(this)">Copy</button>
              </div>
              <pre><code class="code-content lang-curl">${escapeHtml(snippets.curl)}</code><code class="code-content lang-js" style="display:none;">${escapeHtml(snippets.js)}</code><code class="code-content lang-python" style="display:none;">${escapeHtml(snippets.python)}</code></pre>
            </div>
          </div>

          <!-- API Playground Expander -->
          <div class="playground-section">
            <button class="playground-toggle" onclick="window.DocPlayground.togglePlayground(this, '${methodUpper}', '${path}', '${escapeHtml(JSON.stringify(sampleBody))}')">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
              <span>Try It / API Playground</span>
            </button>
            <div class="playground-container" style="display: none;"></div>
          </div>
        </div>
      </div>
    `;
  }

  function switchTab(btn, lang) {
    const parent = btn.closest('.endpoint-body');
    const tabs = parent.querySelectorAll('.snippet-tab');
    tabs.forEach(t => t.classList.remove('active'));
    btn.classList.add('active');

    const codeHeaderLabel = parent.querySelector('.code-lang-label');
    if (codeHeaderLabel) codeHeaderLabel.textContent = lang.toUpperCase();

    const curls = parent.querySelectorAll('.lang-curl');
    const jss = parent.querySelectorAll('.lang-js');
    const pythons = parent.querySelectorAll('.lang-python');

    curls.forEach(c => c.style.display = lang === 'curl' ? 'block' : 'none');
    jss.forEach(c => c.style.display = lang === 'js' ? 'block' : 'none');
    pythons.forEach(c => c.style.display = lang === 'python' ? 'block' : 'none');
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

  async function renderTagEndpoints(tagFilter, targetContainerId) {
    const container = document.getElementById(targetContainerId);
    if (!container) return;

    try {
      const spec = await fetchOpenApiSpec();
      let html = '';
      let count = 0;

      for (const [path, methods] of Object.entries(spec.paths)) {
        for (const [method, operation] of Object.entries(methods)) {
          if (!operation.tags) continue;
          
          const matchesTag = tagFilter === '*' || operation.tags.some(t => t.toLowerCase().includes(tagFilter.toLowerCase()));
          if (matchesTag) {
            html += renderEndpointCard(path, method, operation, spec);
            count++;
          }
        }
      }

      if (count === 0) {
        container.innerHTML = `<div class="card"><p style="color: var(--text-muted);">No endpoints found for tag "${tagFilter}".</p></div>`;
      } else {
        container.innerHTML = html;
      }
    } catch (err) {
      container.innerHTML = `
        <div class="card" style="border-color: #f87171; background-color: rgba(239, 68, 68, 0.05);">
          <h3 style="color: #ef4444; margin-top:0;">API documentation unavailable</h3>
          <p>Failed to load openapi.json: ${err.message}</p>
          <button class="btn-primary" onclick="window.DocOpenApi.retryLoad('${tagFilter}', '${targetContainerId}')">Retry</button>
        </div>
      `;
    }
  }

  async function retryLoad(tagFilter, containerId) {
    openApiData = null;
    await renderTagEndpoints(tagFilter, containerId);
  }

  window.DocOpenApi = {
    fetchOpenApiSpec,
    renderTagEndpoints,
    switchTab,
    retryLoad,
  };
})();
