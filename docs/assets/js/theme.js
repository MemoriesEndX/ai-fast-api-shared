/* Theme handling module (Light / Dark / System) */
(function () {
  const STORAGE_KEY = 'doc_theme_preference';

  function getSavedTheme() {
    return localStorage.getItem(STORAGE_KEY) || 'system';
  }

  function getSystemTheme() {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function applyTheme(theme) {
    const activeTheme = theme === 'system' ? getSystemTheme() : theme;
    document.documentElement.setAttribute('data-theme', activeTheme);

    const themeBtn = document.getElementById('theme-toggle');
    if (themeBtn) {
      themeBtn.setAttribute('title', `Theme: ${theme} (${activeTheme})`);
    }
  }

  function toggleTheme() {
    const current = getSavedTheme();
    let next = 'dark';
    if (current === 'dark') next = 'light';
    else if (current === 'light') next = 'system';
    else next = 'dark';

    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
  }

  // Initialize theme on script load
  const initialTheme = getSavedTheme();
  applyTheme(initialTheme);

  // System change listener
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (getSavedTheme() === 'system') {
      applyTheme('system');
    }
  });

  window.DocTheme = {
    getSavedTheme,
    applyTheme,
    toggleTheme,
  };
})();
