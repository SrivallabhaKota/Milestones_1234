// FinSight Alert System - Right Side Panel with All Button & Date Filtering
(function() {
  'use strict';

  var bellBtn     = document.getElementById('notif-bell-btn');
  var panel       = document.getElementById('alert-panel');
  var overlay     = document.getElementById('alert-panel-overlay');
  var closeBtn    = document.getElementById('alert-panel-close');
  var markAllBtn  = document.getElementById('mark-all-read-btn');
  var alertList   = document.getElementById('alert-list');
  var badge       = document.getElementById('notif-badge');
  var countText   = document.getElementById('alert-count-text');
  var clearAllBtn = document.getElementById('clear-all-btn');

  // Filter elements
  var dateFilter       = document.getElementById('alert-date-filter');
  var allBtn           = document.getElementById('alert-filter-all-btn');
  var resetBtn         = document.getElementById('alert-filter-reset-btn');
  var filterInfo       = document.getElementById('alert-filter-info');
  var filterStatusText = document.getElementById('alert-filter-status-text');

  var currentFilterType = null; // 'date' or null (all)
  var currentFilterVal  = null;

  function openPanel() {
    if (panel) panel.classList.add('open');
    if (overlay) overlay.classList.add('open');
  }
  function closePanel() {
    if (panel) panel.classList.remove('open');
    if (overlay) overlay.classList.remove('open');
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
    if (!dateStr) return '';
    var d = new Date(dateStr);
    var now = new Date();
    var diff = Math.floor((now - d) / 1000);
    if (isNaN(diff)) return dateStr;
    if (diff < 60)    return 'Just now';
    if (diff < 3600)  return Math.floor(diff/60) + 'm ago';
    if (diff < 86400) return Math.floor(diff/3600) + 'h ago';
    return Math.floor(diff/86400) + 'd ago';
  }

  function formatDisplayDate(val) {
    if (!val) return '';
    try {
      var parts = val.split('-');
      if (parts.length === 3) {
        var d = new Date(parts[0], parts[1] - 1, parts[2]);
        return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
      }
    } catch(e){}
    return val;
  }

  function renderAlerts(alerts, unreadCount) {
    if (!alertList) return;
    updateBadge(unreadCount);

    if (!alerts || alerts.length === 0) {
      if (currentFilterType && currentFilterVal) {
        var formattedLabel = formatDisplayDate(currentFilterVal);
        alertList.innerHTML = '<div class="alert-empty"><i class="bi bi-calendar-x" style="font-size:1.5rem; display:block; margin-bottom:8px; opacity:0.6;"></i>No notifications found for <strong>' + formattedLabel + '</strong>.</div>';
      } else {
        alertList.innerHTML = '<div class="alert-empty"><i class="bi bi-check2-circle"></i>All clear! No alerts right now.</div>';
      }
      return;
    }

    alertList.innerHTML = '';
    alerts.forEach(function(a, idx) {
      var item = document.createElement('div');
      item.className = 'alert-item severity-' + (a.severity || 'info') + (a.is_read ? '' : ' unread');
      item.style.animationDelay = (idx * 0.05) + 's';

      var createdDate = a.created_at ? a.created_at.split(' ')[0] : '';
      var timeDisplay = timeAgo(a.created_at);

      item.innerHTML =
        (a.is_read ? '' : '<div class="alert-unread-dot"></div>') +
        '<div class="alert-item-title">' + (a.title || '') + '</div>' +
        '<div class="alert-item-msg">'   + (a.message || '') + '</div>' +
        '<div class="alert-item-footer" style="display:flex; justify-content:space-between; align-items:center; margin-top:8px; font-size:0.71rem; color:rgba(255,255,255,0.45); border-top:1px dashed rgba(255,255,255,0.08); padding-top:6px;">' +
          '<span><i class="bi bi-calendar3 me-1"></i>' + createdDate + '</span>' +
          '<span>' + timeDisplay + '</span>' +
        '</div>';

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
    var url = '/api/alerts';
    var params = [];
    if (currentFilterType === 'date' && currentFilterVal) {
      params.push('date=' + encodeURIComponent(currentFilterVal));
    }

    if (params.length > 0) {
      url += '?' + params.join('&');
    }

    fetch(url)
      .then(function(r){ return r.ok ? r.json() : {alerts:[], unread_count:0}; })
      .then(function(data){ renderAlerts(data.alerts, data.unread_count); })
      .catch(function(){ /* silently skip */ });
  }

  function generateAndLoad() {
    fetch('/api/alerts/generate', {method:'POST'})
      .then(function(){ loadAlerts(); })
      .catch(function(){ loadAlerts(); });
  }

  function updateFilterUI() {
    if (currentFilterType === 'date' && currentFilterVal) {
      if (allBtn) allBtn.classList.remove('active');
      if (resetBtn) resetBtn.style.display = 'inline-flex';
      if (filterInfo) filterInfo.style.display = 'flex';
      if (filterStatusText) filterStatusText.textContent = formatDisplayDate(currentFilterVal) + ' (Day)';
    } else {
      if (allBtn) allBtn.classList.add('active');
      if (resetBtn) resetBtn.style.display = 'none';
      if (filterInfo) filterInfo.style.display = 'none';
      if (dateFilter) dateFilter.value = '';
      currentFilterType = null;
      currentFilterVal = null;
    }
  }

  // Filter Event Listeners
  if (allBtn) {
    allBtn.addEventListener('click', function() {
      currentFilterType = null;
      currentFilterVal = null;
      if (dateFilter) dateFilter.value = '';
      updateFilterUI();
      loadAlerts();
    });
  }

  if (dateFilter) {
    dateFilter.addEventListener('change', function() {
      if (this.value) {
        currentFilterType = 'date';
        currentFilterVal = this.value;
      } else {
        currentFilterType = null;
        currentFilterVal = null;
      }
      updateFilterUI();
      loadAlerts();
    });
  }

  if (resetBtn) {
    resetBtn.addEventListener('click', function() {
      currentFilterType = null;
      currentFilterVal = null;
      if (dateFilter) dateFilter.value = '';
      updateFilterUI();
      loadAlerts();
    });
  }

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
  // Poll every 45 seconds if no filter is active
  setInterval(function() {
    if (!currentFilterType) {
      loadAlerts();
    }
  }, 45000);
})();
