/* Master App Orchestrator & SPA Router */
(function () {
  const routes = {
    'introduction': { title: 'Introduction & Architecture', page: 'pages/introduction.html', tag: null },
    'quick-start': { title: 'Quick Start Guide', page: 'pages/quick-start.html', tag: null },
    'authentication': { title: 'Authentication', page: 'pages/authentication.html', tag: null },
    'chat': { title: 'Chat API Reference', page: 'pages/chat.html', tag: 'Chat' },
    'knowledge': { title: 'Knowledge API Reference', page: 'pages/knowledge.html', tag: 'Knowledge' },
    'pdf-rag': { title: 'PDF RAG API Reference', page: 'pages/pdf-rag.html', tag: 'RAG' },
    'video-rag': { title: 'Video RAG API Reference', page: 'pages/video-rag.html', tag: 'Video RAG' },
    'recommendation': { title: 'Recommendation Engine API', page: 'pages/recommendation.html', tag: 'Recommendation' },
    'lms-tools': { title: 'LMS Tools Integration', page: 'pages/lms-tools.html', tag: 'Tools' },
    'errors': { title: 'Error Catalog', page: 'pages/errors.html', tag: null },
    'examples': { title: 'Code Examples', page: 'pages/examples.html', tag: null },
  };

  async function loadComponent(selector, file) {
    const el = document.querySelector(selector);
    if (!el) return;
    try {
      const res = await fetch(file);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const html = await res.text();
      el.innerHTML = html;
    } catch (e) {
      console.warn(`Could not load component ${file}:`, e);
    }
  }

  async function initApp() {
    // 1. Load Navbar, Sidebar, Search components
    await loadComponent('#navbar-target', 'components/navbar.html');
    await loadComponent('#sidebar-target', 'components/sidebar.html');
    await loadComponent('#search-target', 'components/search.html');

    // 2. Initialize Search & Theme listeners
    if (window.DocSearch) window.DocSearch.initSearch();

    // Mobile menu drawer toggle
    const mobileBtn = document.getElementById('mobile-menu-toggle');
    const sidebar = document.querySelector('.docs-sidebar');
    if (mobileBtn && sidebar) {
      mobileBtn.addEventListener('click', () => {
        sidebar.classList.toggle('mobile-open');
      });
    }

    // Hash router listener
    window.addEventListener('hashchange', handleRoute);
    await handleRoute();
  }

  async function handleRoute() {
    const rawHash = window.location.hash.replace('#', '') || 'introduction';
    const route = routes[rawHash];

    const mainContainer = document.getElementById('main-content-target');
    const sidebar = document.querySelector('.docs-sidebar');
    if (sidebar) sidebar.classList.remove('mobile-open');

    // Update active nav item highlight
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
      if (item.getAttribute('data-page') === rawHash) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    if (!route) {
      render404(rawHash);
      return;
    }

    document.title = `${route.title} - SHARED AI SERVICE Docs`;

    // Skeleton loading state
    mainContainer.innerHTML = `
      <div class="skeleton skeleton-title"></div>
      <div class="skeleton skeleton-text"></div>
      <div class="skeleton skeleton-text" style="width: 80%;"></div>
      <div class="skeleton skeleton-card" style="margin-top: 2rem;"></div>
    `;

    try {
      const res = await fetch(route.page);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const pageHtml = await res.text();
      mainContainer.innerHTML = pageHtml;

      // If page renders OpenAPI endpoints, call openapi.js
      const endpointTarget = mainContainer.querySelector('[data-openapi-tag]');
      if (endpointTarget && window.DocOpenApi) {
        const tag = endpointTarget.getAttribute('data-openapi-tag');
        await window.DocOpenApi.renderTagEndpoints(tag, endpointTarget.id);
      }

      window.scrollTo(0, 0);
    } catch (err) {
      mainContainer.innerHTML = `
        <div class="card" style="border-color: #f87171;">
          <h2 style="color: #ef4444;">Page unavailable</h2>
          <p>Could not load documentation page: ${err.message}</p>
          <button class="btn-primary" onclick="window.DocApp.handleRoute()">Retry</button>
        </div>
      `;
    }
  }

  function render404(hash) {
    document.title = '404 Page Not Found - SHARED AI SERVICE Docs';
    const mainContainer = document.getElementById('main-content-target');
    mainContainer.innerHTML = `
      <div class="card" style="text-align: center; padding: 4rem 2rem;">
        <h1 style="font-size: 3rem; margin-bottom: 0.5rem; color: var(--accent-primary);">404</h1>
        <h2>Documentation page not found</h2>
        <p style="margin-bottom: 2rem;">The requested section <code>#${hash}</code> does not exist.</p>
        <div style="display: flex; gap: 1rem; justify-content: center;">
          <a href="#introduction" class="btn-primary" style="text-decoration: none;">Back to Documentation</a>
          <button class="btn-secondary" onclick="window.DocSearch.openSearch()">Search Documentation</button>
        </div>
      </div>
    `;
  }

  function copyCodeBlock(btn) {
    const container = btn.closest('.code-block-container');
    const code = container.querySelector('code:not([style*="display: none"])') || container.querySelector('code');
    if (!code) return;

    navigator.clipboard.writeText(code.textContent).then(() => {
      const origText = btn.innerText;
      btn.innerText = 'Copied ✓';
      setTimeout(() => { btn.innerText = origText; }, 2000);
    });
  }

  document.addEventListener('DOMContentLoaded', initApp);

  window.DocApp = {
    initApp,
    handleRoute,
    copyCodeBlock,
  };
})();
