/**
 * ============================================================
 * BP Central TI — Theme Manager Module
 * Gerenciador de Estados de Tema (Modo Escuro / Modo Claro)
 * Padrão: Singleton / State Pattern
 * ============================================================
 */
(function (global) {
  'use strict';

  const STORAGE_KEY = 'bp_central_ti_theme';
  const THEMES = {
    DARK: 'dark',
    LIGHT: 'light'
  };
  const ICONS = {
    DARK: '🌙',
    LIGHT: '☀️'
  };

  /**
   * Valida e sanitiza o valor do tema para evitar manipulação de estado.
   * @param {string|null} val
   * @returns {'dark'|'light'}
   */
  function sanitizeTheme(val) {
    return val === THEMES.LIGHT ? THEMES.LIGHT : THEMES.DARK;
  }

  /**
   * Obtém o tema persistido ou retorna o padrão (dark).
   * @returns {'dark'|'light'}
   */
  function getStoredTheme() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return sanitizeTheme(stored);
    } catch (e) {
      console.warn('[ThemeManager] Não foi possível acessar o localStorage:', e);
      return THEMES.DARK;
    }
  }

  /**
   * Atualiza a árvore do DOM e os elementos visuais do botão de alternância.
   * @param {'dark'|'light'} theme
   */
  function applyThemeToDOM(theme) {
    document.documentElement.setAttribute('data-theme', theme);

    // Atualiza ícones dos botões de alternância presentes na tela
    const iconElements = document.querySelectorAll('.theme-toggle-icon, #theme-icon');
    iconElements.forEach(function (el) {
      el.textContent = theme === THEMES.LIGHT ? ICONS.LIGHT : ICONS.DARK;
    });

    const toggleButtons = document.querySelectorAll('.theme-toggle-btn, #theme-toggle-btn');
    toggleButtons.forEach(function (btn) {
      const isLight = theme === THEMES.LIGHT;
      btn.setAttribute('aria-label', isLight ? 'Alternar para Modo Escuro' : 'Alternar para Modo Claro');
      btn.setAttribute('title', isLight ? 'Mudar para Modo Escuro (Alt+T)' : 'Mudar para Modo Claro (Alt+T)');
    });
  }

  /**
   * Salva o tema no localStorage e sincroniza a UI.
   * @param {'dark'|'light'} theme
   */
  function setTheme(theme) {
    const validTheme = sanitizeTheme(theme);
    try {
      localStorage.setItem(STORAGE_KEY, validTheme);
    } catch (e) {
      console.warn('[ThemeManager] Falha ao persistir no localStorage:', e);
    }

    applyThemeToDOM(validTheme);

    // Dispara evento customizado para outros componentes
    try {
      window.dispatchEvent(new CustomEvent('bp-theme-change', {
        detail: { theme: validTheme }
      }));
    } catch (_) {}
  }

  /**
   * Alterna entre Modo Claro e Modo Escuro.
   */
  function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || THEMES.DARK;
    const next = current === THEMES.LIGHT ? THEMES.DARK : THEMES.LIGHT;
    setTheme(next);
  }

  /**
   * Inicialização do gerenciador ao carregar a página.
   */
  function init() {
    const active = getStoredTheme();
    applyThemeToDOM(active);

    // Atalho de teclado opcional (Alt + T) para alternar tema
    window.addEventListener('keydown', function (e) {
      if (e.altKey && (e.key === 't' || e.key === 'T')) {
        e.preventDefault();
        toggleTheme();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Exportação segura do Singleton
  global.ThemeManager = {
    init: init,
    toggleTheme: toggleTheme,
    setTheme: setTheme,
    getTheme: function () {
      return document.documentElement.getAttribute('data-theme') || THEMES.DARK;
    },
    THEMES: THEMES
  };
})(typeof window !== 'undefined' ? window : this);
