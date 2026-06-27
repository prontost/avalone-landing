/**
 * Client-side helpers that mirror the shared Avalone widgets (Card, Button, PageHeader).
 * Use these in dynamic JS instead of hardcoding markup and inline styles.
 */
(function (root) {
  'use strict';

  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
    );
  }

  function attrsString(attrs) {
    if (!attrs) return '';
    return Object.entries(attrs)
      .map(([k, v]) => {
        if (v === true) return escapeHtml(k);
        if (v == null || v === false) return '';
        return `${escapeHtml(k)}="${escapeHtml(v)}"`;
      })
      .filter(Boolean)
      .join(' ');
  }

  const Avalone = {
    escapeHtml,

    /**
     * Card widget.
     * opts: { title?: string, children: string (HTML), extraClass?: string }
     */
    card(opts = {}) {
      const cls = ['avalone-card', opts.extraClass].filter(Boolean).join(' ');
      const title = opts.title
        ? `<h3 class="avalone-card__title">${escapeHtml(opts.title)}</h3>`
        : '';
      return `<div class="${cls}">${title}${opts.children || ''}</div>`;
    },

    /**
     * Button widget.
     * opts: { label: string, variant?: 'primary'|'secondary'|'ghost'|'danger',
     *         size?: 'sm', extraClass?: string, attrs?: object }
     * attrs are rendered as HTML attributes (onclick, data-*, etc.).
     */
    button(opts = {}) {
      const variant = opts.variant || 'primary';
      const cls = ['avalone-btn', `avalone-btn-${variant}`, opts.size ? `avalone-btn-${opts.size}` : '', opts.extraClass]
        .filter(Boolean)
        .join(' ');
      const attr = attrsString(opts.attrs);
      return `<button class="${cls}" ${attr}>${opts.label || ''}</button>`;
    },

    /**
     * Page header widget.
     * opts: { title: string, actions?: string (HTML) }
     */
    pageHeader(opts = {}) {
      const actions = opts.actions
        ? `<div class="avalone-page-header__actions">${opts.actions}</div>`
        : '';
      return `<header class="avalone-page-header"><h1 class="avalone-page-header__title">${escapeHtml(opts.title)}</h1>${actions}</header>`;
    },
  };

  root.Avalone = Avalone;
})(typeof window !== 'undefined' ? window : globalThis);
