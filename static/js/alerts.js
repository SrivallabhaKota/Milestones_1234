// FinSight Alert System - Right Side Panel
(function() {
  'use strict';

  var bellBtn    = document.getElementById('notif-bell-btn');
  var panel      = document.getElementById('alert-panel');
  var overlay    = document.getElementById('alert-panel-overlay');
  var closeBtn   = document.getElementById('alert-panel-close');
  var markAllBtn = document.getElementById('mark-all-read-btn');
  var alertList  = document.getElementById('alert-list');
  var badge      = document.getElementById('notif-badge');
  var countText  = document.getElementById('alert-count-text');

  function openPanel() {
    panel.classList.add('open');
    overlay.classList.add('open');
  }
  function closePanel() {
    panel.classList.remove('open');
    overlay.classList.remove('open');
  }

  if (bellBtn) bellBtn.addEventListener('click', function(e) { e.stopPropagation(); openPanel(); });
  if (closeBtn) closeBtn.addEventListener('click', closePanel);
  if (overlay)  overlay.addEventListener('click', closePanel);

  function updateBadge(count) {
    if (!badge) return;
    if (count > 0) {
      badge.textContent = count > 99 ? '99+' : count;
      badge.classList.remove('hidden');
    } else {
      badge.classList.add('hidden');
    }
    if (countText) countText.textContent = count + ' Unread';
  }

  function timeAgo(dateStr) {
    var d = new Date(dateStr);
    var now = new Date();
    var diff = Math.floor((now - d) / 1000);
    if (diff < 60)    return 'Just now';
    if (diff < 3600)  return Math.floor(diff/60) + 'm ago';
    if (diff < 86400) return Math.floor(diff/3600) + 'h ago';
    return Math.floor(diff/86400) + 'd ago';
  }

  function renderAlerts(alerts, unreadCount) {
    if (!alertList) return;
    updateBadge(unreadCount);
    if (!alerts || alerts.length === 0) {
      alertList.innerHTML = '<div class="alert-empty"><i class="bi bi-check2-circle"></i>All clear! No alerts right now.</div>';
      return;
    }
    alertList.innerHTML = '';
    alerts.forEach(function(a, idx) {
      var item = document.createElement('div');
      item.className = 'alert-item severity-' + (a.severity || 'info') + (a.is_read ? '' : ' unread');
      item.style.animationDelay = (idx * 0.05) + 's';
      item.innerHTML =
        (a.is_read ? '' : '<div class="alert-unread-dot"></div>') +
        '<div class="alert-item-title">' + (a.title || '') + '</div>' +
        '<div class="alert-item-msg">'   + (a.message || '') + '</div>' +
        '<div class="alert-item-time">'  + timeAgo(a.created_at) + '</div>';
      item.addEventListener('click', function() {
        if (!a.is_read) {
          fetch('/api/alerts/mark-read', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({alert_id: a.id})
          }).then(function() {
            item.classList.remove('unread');
            var dot = item.querySelector('.alert-unread-dot');
            if (dot) dot.remove();
            a.is_read = true;
            var curCount = parseInt((badge ? badge.textContent : '0')) || 0;
            if (curCount > 0) updateBadge(curCount - 1);
          });
        }
      });
      alertList.appendChild(item);
    });
  }

  function loadAlerts() {
    fetch('/api/alerts')
      .then(function(r){ return r.ok ? r.json() : {alerts:[], unread_count:0}; })
      .then(function(data){ renderAlerts(data.alerts, data.unread_count); })
      .catch(function(){ /* silently skip */ });
  }

  function generateAndLoad() {
    fetch('/api/alerts/generate', {method:'POST'})
      .then(function(){ loadAlerts(); })
      .catch(function(){ loadAlerts(); });
  }

  
  var clearAllBtn = document.getElementById('clear-all-btn');
  if (clearAllBtn) {
    clearAllBtn.addEventListener('click', function() {
      if (confirm('Are you sure you want to clear all notifications?')) {
        fetch('/api/alerts/clear', {method:'POST'})
          .then(function(){ loadAlerts(); });
      }
    });
  }
if (markAllBtn) {
    markAllBtn.addEventListener('click', function() {
      fetch('/api/alerts/mark-read', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({})})
        .then(function(){ loadAlerts(); });
    });
  }

  // Initial load
  generateAndLoad();
  // Poll every 45 seconds
  setInterval(loadAlerts, 45000);
})();
