/* Avalone shared shell JS */

const AVALONE_I18N = window.AVALONE_I18N || {};

(function() {
  'use strict';

  const $ = (id) => document.getElementById(id);

  // Theme
  function initTheme() {
    const saved = localStorage.getItem('avalone_theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const isDark = saved ? saved === 'dark' : prefersDark;
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
  }

  window.toggleTheme = function() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('avalone_theme', next);
  };

  // App switcher
  function initAppSwitcher() {
    const switcher = document.querySelector('.avalone-app-switcher');
    if (!switcher) return;
    const btn = switcher.querySelector('.avalone-app-switcher__btn');
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      switcher.classList.toggle('open');
    });
    document.addEventListener('click', () => switcher.classList.remove('open'));
  }

  // Profile menu
  function initProfileMenu() {
    const profile = document.querySelector('.avalone-profile');
    if (!profile) return;
    const avatar = profile.querySelector('.avalone-profile__avatar');
    const menu = profile.querySelector('.avalone-profile__menu');
    if (!menu || !avatar) return;
    avatar.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = menu.classList.toggle('open');
      avatar.setAttribute('aria-expanded', String(isOpen));
    });
    document.addEventListener('click', () => {
      menu.classList.remove('open');
      avatar.setAttribute('aria-expanded', 'false');
    });
  }

  // Notifications
  async function updateNotificationCount() {
    const badge = document.querySelector('.avalone-notifications__count');
    if (!badge) return;
    try {
      const res = await fetch('/api/notifications/unread-count', { credentials: 'same-origin' });
      if (!res.ok) return;
      const data = await res.json();
      const count = data.count || 0;
      badge.textContent = count > 99 ? '99+' : String(count);
      badge.style.display = count ? 'inline-flex' : 'none';
    } catch (e) {
      // silently fail
    }
  }

  window.openNotifications = function() {
    const panel = document.querySelector('.avalone-notifications__panel');
    if (panel) panel.classList.toggle('open');
  };

  // Burger menu
  window.toggleAvaloneMenu = function() {
    const menu = document.getElementById('avalone-menu');
    if (!menu) return;
    const isOpen = menu.classList.toggle('open');
    menu.setAttribute('aria-hidden', String(!isOpen));
    const btn = document.querySelector('.avalone-menu__toggle');
    if (btn) btn.setAttribute('aria-expanded', String(isOpen));
    document.body.style.overflow = isOpen ? 'hidden' : '';
  };

  window.closeAvaloneMenu = function() {
    const menu = document.getElementById('avalone-menu');
    if (!menu) return;
    menu.classList.remove('open');
    menu.setAttribute('aria-hidden', 'true');
    const btn = document.querySelector('.avalone-menu__toggle');
    if (btn) btn.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  };

  // Language
  window.setLang = async function(lang) {
    localStorage.setItem('avalone_lang', lang);
    document.documentElement.lang = lang === 'auto' ? 'ru' : lang;
    try {
      await fetch('/api/lang', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lang: lang }),
        credentials: 'same-origin',
      });
    } catch (e) {
      // offline / unauth — localStorage is enough
    }
    window.location.reload();
  };

  // Invite / share Avalone (single entry point in the burger menu)
  let _inviteUrl = 'https://avalone.online';

  async function loadInviteUrl() {
    let url = 'https://avalone.online';
    try {
      const res = await fetch('/api/referral/code', { credentials: 'same-origin' });
      if (res.ok) {
        const data = await res.json();
        if (data.url) url = data.url;
        else if (data.code) url = url + '?ref=' + encodeURIComponent(data.code);
      }
    } catch (e) {
      // referral API optional
    }
    _inviteUrl = url;
    return url;
  }

  window.openInviteModal = async function() {
    closeAvaloneMenu();
    const url = await loadInviteUrl();
    const modal = document.getElementById('avalone-invite-modal');
    const qrImg = document.getElementById('avalone-invite-qr-img');
    if (qrImg) {
      qrImg.src = '/finance/qr?url=' + encodeURIComponent(url) + '&size=200';
      qrImg.style.display = 'block';
    }
    if (modal) {
      modal.classList.add('open');
      modal.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
    }
  };

  window.closeInviteModal = function() {
    const modal = document.getElementById('avalone-invite-modal');
    if (modal) {
      modal.classList.remove('open');
      modal.setAttribute('aria-hidden', 'true');
      document.body.style.overflow = '';
    }
  };

  window.shareInviteLink = async function() {
    const url = _inviteUrl;
    const text = AVALONE_I18N.share_text || document.title;
    if (navigator.share) {
      try { await navigator.share({ title: document.title, text, url }); return; } catch (e) {}
    }
    copyInviteLink();
  };

  window.copyInviteLink = async function() {
    const url = _inviteUrl;
    try {
      await navigator.clipboard.writeText(url);
      if (window.toast) window.toast(AVALONE_I18N.toast_share_link_copied || 'Link copied');
    } catch (e) {
      prompt(AVALONE_I18N.share_copy_prompt || 'Copy link:', url);
    }
  };

  // Feedback modal
  window.openFeedbackModal = function() {
    closeAvaloneMenu();
    const modal = document.getElementById('avalone-feedback-modal');
    if (modal) {
      modal.classList.add('open');
      modal.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
    }
  };

  window.closeFeedbackModal = function() {
    const modal = document.getElementById('avalone-feedback-modal');
    if (modal) {
      modal.classList.remove('open');
      modal.setAttribute('aria-hidden', 'true');
      document.body.style.overflow = '';
    }
  };

  window.submitShellFeedback = function(e) {
    e.preventDefault();
    const form = e.target;
    const status = document.getElementById('avalone-feedback-status');
    const message = form.querySelector('[name="message"]').value.trim();
    const contact = form.querySelector('[name="contact"]').value.trim();
    if (!message) return false;
    status.style.display = 'none';
    fetch('/api/feedback', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: message, contact: contact, source_page: location.href}),
      credentials: 'same-origin'
    }).then(function(r){
      if(r.ok){
        status.textContent = AVALONE_I18N.feedback_thanks || 'Thank you';
        status.className = 'feedback-status text-success';
        form.reset();
      }else{
        status.textContent = AVALONE_I18N.feedback_error || 'Could not send';
        status.className = 'feedback-status text-danger';
      }
      status.style.display = 'block';
    }).catch(function(){
      status.textContent = AVALONE_I18N.feedback_error || 'Could not send';
      status.className = 'feedback-status text-danger';
      status.style.display = 'block';
    });
    return false;
  };

  // Multi-profile dropdown
  window.toggleProfileDropdown = function() {
    const dropdown = document.getElementById('avalone-profile-dropdown');
    const switcher = document.querySelector('.avalone-profile-switcher');
    if (dropdown) dropdown.classList.toggle('open');
    if (switcher) switcher.classList.toggle('open');
  };

  // Auth modal
  function _authModal() { return document.getElementById('avalone-auth-modal'); }
  function _authStatus() { return document.getElementById('auth-modal-status'); }

  window.openAuthModal = function(mode, token) {
    closeAvaloneMenu();
    const modal = _authModal();
    if (!modal) return;
    if (mode) switchAuthView(mode, token);
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  };

  window.closeAuthModal = function() {
    const modal = _authModal();
    if (!modal) return;
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  };

  window.switchAuthView = function(mode, token) {
    const modal = _authModal();
    if (!modal) return;
    const panels = modal.querySelectorAll('.auth-panel');
    panels.forEach(function(p){ p.classList.remove('active'); });
    const tabs = modal.querySelectorAll('.avalone-auth-tab');
    tabs.forEach(function(t){ t.classList.remove('active'); });

    const target = modal.querySelector('#auth-' + mode + '-panel');
    if (target) target.classList.add('active');

    if (mode === 'login') {
      modal.querySelector('[data-target="auth-login-panel"]')?.classList.add('active');
    } else if (mode === 'register') {
      modal.querySelector('[data-target="auth-register-panel"]')?.classList.add('active');
    } else {
      tabs.forEach(function(t){ t.classList.remove('active'); });
    }

    if (token && mode === 'reset') {
      const input = modal.querySelector('#auth-reset-panel input[name="token"]');
      if (input) input.value = token;
    }

    const title = document.getElementById('auth-modal-title');
    if (title) {
      const titles = {
        login: AVALONE_I18N.auth_login_title || 'Sign in',
        register: AVALONE_I18N.auth_register_title || 'Sign up',
        forgot: AVALONE_I18N.reset_forgot_title || 'Password recovery',
        reset: AVALONE_I18N.reset_title || 'New password'
      };
      title.textContent = titles[mode] || titles.login;
    }
    const status = _authStatus();
    if (status) status.style.display = 'none';
  };

  window.submitAuthForm = function(form, mode) {
    const status = _authStatus();
    if (status) status.style.display = 'none';
    const endpoints = {
      login: '/api/auth/login',
      register: '/api/auth/register',
      forgot: '/api/auth/forgot-password',
      reset: '/api/auth/reset-password'
    };
    const url = endpoints[mode];
    if (!url) return false;
    const data = new FormData(form);
    const body = {};
    data.forEach(function(value, key){ body[key] = value; });
    fetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
      credentials: 'same-origin'
    }).then(function(r){
      return r.json().then(function(payload){
        if (r.ok && payload.ok) {
          if (mode === 'forgot') {
            if (status) {
              status.textContent = payload.message || AVALONE_I18N.reset_email_sent || 'Link sent';
              status.className = 'auth-status success';
              status.style.display = 'block';
            }
            form.reset();
          } else {
            // login/register/reset: reload to apply new session
            location.href = payload.next || '/';
          }
        } else {
          if (status) {
            status.textContent = payload.error || AVALONE_I18N.auth_error_invalid_credentials || 'Error';
            status.className = 'auth-status error';
            status.style.display = 'block';
          }
        }
      });
    }).catch(function(){
      if (status) {
        status.textContent = AVALONE_I18N.auth_error_invalid_credentials || 'Error';
        status.className = 'auth-status error';
        status.style.display = 'block';
      }
    });
    return false;
  };

  // Auto-open modal from URL ?mode=reset&token=...
  (function _autoOpenAuthModal(){
    const params = new URLSearchParams(location.search);
    const mode = params.get('mode');
    const token = params.get('token');
    if (mode && document.getElementById('avalone-auth-modal')) {
      openAuthModal(mode, token);
    }
  })();

  // Search overlay
  window.openGlobalSearch = function() {
    const overlay = document.getElementById('global-search-overlay');
    if (!overlay) return;
    overlay.classList.add('open');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    const input = overlay.querySelector('.avalone-search-overlay__input');
    if (input) setTimeout(() => input.focus(), 50);
  };
  window.closeGlobalSearch = function() {
    const overlay = document.getElementById('global-search-overlay');
    if (!overlay) return;
    overlay.classList.remove('open');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  };

  // Device / screen-time heartbeat
  function generateDeviceId() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    let id = '';
    for (let i = 0; i < 8; i++) {
      id += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return id;
  }

  function getDeviceId() {
    try {
      let id = localStorage.getItem('avalone_device_id');
      if (!id) {
        id = generateDeviceId();
        localStorage.setItem('avalone_device_id', id);
      }
      return id;
    } catch (e) {
      return generateDeviceId();
    }
  }

  function sendHeartbeat(seconds) {
    const payload = {
      device_id: getDeviceId(),
      screen: window.screen ? `${window.screen.width}x${window.screen.height}` : '0x0',
      platform: navigator.platform || '',
      seconds: seconds || 5,
    };
    const options = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      credentials: 'same-origin',
    };
    if (navigator.sendBeacon) {
      navigator.sendBeacon('/api/heartbeat', new Blob([options.body], { type: 'application/json' }));
      return;
    }
    fetch('/api/heartbeat', options).catch(() => {});
  }

  function DeviceTracker() {
    this.unauthorizedCount = 0;
    this.intervalId = null;
    this.boundVisibility = null;
    this.boundUnload = null;
  }

  DeviceTracker.prototype.start = function() {
    if (this.intervalId) return;
    this.unauthorizedCount = 0;
    const tick = async () => {
      if (document.hidden) return;
      try {
        const res = await fetch('/api/heartbeat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            device_id: getDeviceId(),
            screen: window.screen ? `${window.screen.width}x${window.screen.height}` : '0x0',
            platform: navigator.platform || '',
            seconds: 5,
          }),
          credentials: 'same-origin',
        });
        if (res.status === 401) {
          this.unauthorizedCount += 1;
          if (this.unauthorizedCount >= 2) this.stop();
        } else {
          this.unauthorizedCount = 0;
        }
      } catch (e) {
        // offline / transient — keep trying
      }
    };
    this.intervalId = setInterval(tick, 5000);

    this.boundVisibility = () => {
      if (document.hidden) {
        sendHeartbeat(5);
      }
    };
    this.boundUnload = () => sendHeartbeat(5);
    document.addEventListener('visibilitychange', this.boundVisibility);
    window.addEventListener('beforeunload', this.boundUnload);
  };

  DeviceTracker.prototype.stop = function() {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    if (this.boundVisibility) {
      document.removeEventListener('visibilitychange', this.boundVisibility);
      this.boundVisibility = null;
    }
    if (this.boundUnload) {
      window.removeEventListener('beforeunload', this.boundUnload);
      this.boundUnload = null;
    }
  };

  window.AvaloneDeviceTracker = DeviceTracker;

  function initHeartbeat() {
    const tracker = new DeviceTracker();
    tracker.start();
  }

  function init() {
    initTheme();
    initAppSwitcher();
    initProfileMenu();
    updateNotificationCount();
    setInterval(updateNotificationCount, 60000);
    if (document.body && document.body.dataset.avaloneAuthenticated === '1') {
      initHeartbeat();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
