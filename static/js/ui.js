(function () {
  let stack = document.querySelector('.toast-stack');
  if (!stack) {
    stack = document.createElement('div');
    stack.className = 'toast-stack';
    document.body.appendChild(stack);
  }

  const ICONS = { success: '\u2713', error: '!', default: '' };

  window.showToast = function (message, type = 'default') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icon = ICONS[type] || '';
    toast.innerHTML = icon ? `<span>${icon}</span><span>${message}</span>` : `<span>${message}</span>`;
    stack.appendChild(toast);

    setTimeout(() => {
      toast.classList.add('leaving');
      setTimeout(() => toast.remove(), 250);
    }, 2800);
  };
})();

window.animateCount = function (el, to, opts = {}) {
  const duration = opts.duration || 1000;
  const suffix = opts.suffix || '';
  const from = 0;
  const start = performance.now();

  function tick(now) {
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 4);
    const value = Math.round(from + (to - from) * eased);
    el.textContent = value + suffix;
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
};

window.staggerRows = function (container, selector) {
  const rows = container.querySelectorAll(selector);
  rows.forEach((row, i) => {
    row.classList.add('row-enter');
    row.style.animationDelay = `${i * 70}ms`;
  });
};

window.pulseRow = function (el) {
  if (!el) return;
  el.classList.remove('row-pulse');
  void el.offsetWidth;
  el.classList.add('row-pulse');
};

// ---------- Avatars: initials + consistent color from name ----------
const AVATAR_COLORS = ['#7C3AED', '#3B82F6', '#3F9142', '#DB5C7A', '#B45309', '#0EA5A5', '#C2410C'];

window.getInitials = function (name) {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
};

window.avatarColor = function (name) {
  if (!name) return AVATAR_COLORS[0];
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
};

window.avatarHtml = function (name, sizeClass = '') {
  const initials = getInitials(name);
  const color = avatarColor(name);
  return `<div class="avatar ${sizeClass}" style="background:${color}">${initials}</div>`;
};

// ---------- Notifications dropdown (wired on pages that include the bell) ----------
(function () {
  const bell = document.getElementById('notif-bell');
  if (!bell) return;

  const dropdown = document.getElementById('notif-dropdown');
  const list = document.getElementById('notif-list');
  const dot = document.getElementById('notif-dot');
  const markAllBtn = document.getElementById('notif-mark-all');

  function timeAgo(iso) {
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  }

  async function loadNotifications() {
    const res = await fetch('/notifications');
    if (res.status === 401) return;
    const data = await res.json();

    if (data.unread_count > 0) {
      dot.textContent = data.unread_count > 9 ? '9+' : data.unread_count;
      dot.style.display = 'flex';
    } else {
      dot.style.display = 'none';
    }

    list.innerHTML = data.notifications.length
      ? data.notifications.map(n => `
          <div class="notif-item ${n.read ? '' : 'unread'}">
            <span class="notif-item-dot"></span>
            <div class="notif-item-body">
              <div>${n.message}</div>
              <div class="notif-item-time">${timeAgo(n.created_at)}</div>
            </div>
          </div>`).join('')
      : '<div class="search-empty">No notifications yet</div>';
  }

  bell.addEventListener('click', async (e) => {
    e.stopPropagation();
    dropdown.classList.toggle('visible');
    if (dropdown.classList.contains('visible')) await loadNotifications();
  });

  document.addEventListener('click', (e) => {
    if (!dropdown.contains(e.target) && e.target !== bell) dropdown.classList.remove('visible');
  });

  if (markAllBtn) {
    markAllBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      await fetch('/notifications/read-all', { method: 'PATCH' });
      loadNotifications();
    });
  }

  loadNotifications();
})();

// ---------- Search bar (wired on pages that include it) ----------
(function () {
  const input = document.getElementById('global-search');
  if (!input) return;

  const results = document.getElementById('search-results');
  let debounceTimer = null;

  input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    const q = input.value.trim();
    if (!q) { results.classList.remove('visible'); return; }

    debounceTimer = setTimeout(async () => {
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
      if (res.status !== 200) return;
      const data = await res.json();
      const items = [
        ...data.tasks.map(t => ({ type: 'Task', title: t.title, href: '/tasks-page' })),
        ...data.help_requests.map(h => ({ type: 'Help', title: h.title, href: '/help-page' })),
      ];
      results.innerHTML = items.length
        ? items.map(i => `
            <div class="search-result-item" onclick="window.location.href='${i.href}'">
              <div class="search-result-type">${i.type}</div>
              <div>${i.title}</div>
            </div>`).join('')
        : '<div class="search-empty">No matches</div>';
      results.classList.add('visible');
    }, 250);
  });

  document.addEventListener('click', (e) => {
    if (!results.contains(e.target) && e.target !== input) results.classList.remove('visible');
  });
})();
