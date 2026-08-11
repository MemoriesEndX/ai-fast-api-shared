/* Search Module - Real-time OpenAPI & Page Search (Ctrl + K) */
(function () {
  let isModalOpen = false;

  function initSearch() {
    const searchTrigger = document.getElementById('nav-search-trigger');
    const modal = document.getElementById('search-modal');
    const modalClose = document.getElementById('search-modal-close');
    const input = document.getElementById('search-modal-input');

    if (searchTrigger) {
      searchTrigger.addEventListener('click', openSearch);
    }
    if (modalClose) {
      modalClose.addEventListener('click', closeSearch);
    }
    if (modal) {
      modal.addEventListener('click', (e) => {
        if (e.target === modal) closeSearch();
      });
    }
    if (input) {
      input.addEventListener('input', handleSearchInput);
    }

    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (isModalOpen) closeSearch();
        else openSearch();
      }
      if (e.key === 'Escape' && isModalOpen) {
        closeSearch();
      }
    });
  }

  function openSearch() {
    const modal = document.getElementById('search-modal');
    const input = document.getElementById('search-modal-input');
    if (!modal) return;
    modal.classList.add('open');
    isModalOpen = true;
    if (input) {
      input.value = '';
      input.focus();
    }
    handleSearchInput();
  }

  function closeSearch() {
    const modal = document.getElementById('search-modal');
    if (!modal) return;
    modal.classList.remove('open');
    isModalOpen = false;
  }

  async function handleSearchInput() {
    const input = document.getElementById('search-modal-input');
    const resultsContainer = document.getElementById('search-modal-results');
    if (!input || !resultsContainer) return;

    const query = input.value.trim().toLowerCase();
    if (!query) {
      resultsContainer.innerHTML = `
        <div style="padding: 2rem; text-align: center; color: var(--text-muted); font-size: 0.9rem;">
          Type to search endpoints, paths, tags, or guides...
        </div>
      `;
      return;
    }

    const results = [];

    // Static pages search
    const staticPages = [
      { title: 'Introduction & Architecture', path: '#introduction', category: 'Guide' },
      { title: 'Quick Start Guide', path: '#quick-start', category: 'Guide' },
      { title: 'Authentication & API Keys', path: '#authentication', category: 'Guide' },
      { title: 'Error Codes Catalog', path: '#errors', category: 'Guide' },
      { title: 'Code Examples (cURL, JS, Python)', path: '#examples', category: 'Guide' },
    ];
    for (const page of staticPages) {
      if (page.title.toLowerCase().includes(query) || page.category.toLowerCase().includes(query)) {
        results.push(page);
      }
    }

    // OpenAPI Search
    try {
      if (window.DocOpenApi) {
        const spec = await window.DocOpenApi.fetchOpenApiSpec();
        if (spec && spec.paths) {
          for (const [path, methods] of Object.entries(spec.paths)) {
            for (const [method, op] of Object.entries(methods)) {
              const summary = op.summary || '';
              const desc = op.description || '';
              const tags = (op.tags || []).join(' ');

              if (
                path.toLowerCase().includes(query) ||
                method.toLowerCase().includes(query) ||
                summary.toLowerCase().includes(query) ||
                desc.toLowerCase().includes(query) ||
                tags.toLowerCase().includes(query)
              ) {
                // Determine target hash page from tag
                let pageHash = '#chat';
                if (tags.toLowerCase().includes('knowledge')) pageHash = '#knowledge';
                else if (tags.toLowerCase().includes('pdf') || tags.toLowerCase().includes('rag')) pageHash = '#pdf-rag';
                else if (tags.toLowerCase().includes('video')) pageHash = '#video-rag';
                else if (tags.toLowerCase().includes('recommend')) pageHash = '#recommendation';
                else if (tags.toLowerCase().includes('tools')) pageHash = '#lms-tools';

                results.push({
                  title: `${method.toUpperCase()} ${path}`,
                  subtitle: summary,
                  path: pageHash,
                  category: `API Endpoint (${method.toUpperCase()})`,
                  method: method.toUpperCase(),
                });
              }
            }
          }
        }
      }
    } catch (e) {
      // Ignore openapi load failure in search fallback
    }

    if (results.length === 0) {
      resultsContainer.innerHTML = `
        <div style="padding: 2rem; text-align: center; color: var(--text-muted); font-size: 0.9rem;">
          No results found for "${query}"
        </div>
      `;
      return;
    }

    let html = '';
    for (const r of results) {
      const methodBadge = r.method ? `<span class="method-tag method-${r.method.toLowerCase()}">${r.method}</span>` : '';
      html += `
        <a href="${r.path}" class="search-result-item" onclick="window.DocSearch.closeSearch()">
          <div class="result-info">
            <div class="result-title">${r.title} ${methodBadge}</div>
            <div class="result-path">${r.subtitle || r.category}</div>
          </div>
          <span style="font-size: 0.75rem; color: var(--text-muted);">${r.category}</span>
        </a>
      `;
    }
    resultsContainer.innerHTML = html;
  }

  window.DocSearch = {
    initSearch,
    openSearch,
    closeSearch,
  };
})();
