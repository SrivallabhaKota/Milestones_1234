// FinSight Dark & Light Mode Theme Toggle Manager
(function() {
  'use strict';

  function applyTheme(theme) {
    if (theme === 'light') {
      document.documentElement.classList.add('light-mode');
      document.body.classList.add('light-mode');
      document.body.classList.remove('dark-mode');
    } else {
      document.documentElement.classList.remove('light-mode');
      document.body.classList.remove('light-mode');
      document.body.classList.add('dark-mode');
    }
    updateToggleButton(theme);
  }

  function updateToggleButton(theme) {
    var btn = document.getElementById('theme-toggle-btn');
    if (!btn) return;

    if (theme === 'light') {
      btn.innerHTML = '<i class="bi bi-moon-stars-fill" style="color: #6366F1;"></i>';
      btn.setAttribute('title', 'Switch to Dark Mode');
      btn.setAttribute('aria-label', 'Switch to Dark Mode');
    } else {
      btn.innerHTML = '<i class="bi bi-sun-fill" style="color: #FBBF24;"></i>';
      btn.setAttribute('title', 'Switch to Light Mode');
      btn.setAttribute('aria-label', 'Switch to Light Mode');
    }
  }

  function initThemeToggle() {
    var savedTheme = localStorage.getItem('finsight_theme') || 'dark';
    
    // Create floating theme toggle button if not already in document
    var btn = document.getElementById('theme-toggle-btn');
    if (!btn) {
      btn = document.createElement('button');
      btn.id = 'theme-toggle-btn';
      btn.className = 'theme-toggle-btn';
      btn.type = 'button';
      document.body.appendChild(btn);
    }

    applyTheme(savedTheme);

    btn.onclick = function() {
      var currentTheme = localStorage.getItem('finsight_theme') || 'dark';
      var newTheme = (currentTheme === 'dark') ? 'light' : 'dark';
      localStorage.setItem('finsight_theme', newTheme);
      applyTheme(newTheme);
    };
  }

  // Early theme apply on script load to prevent white/dark flashes
  var earlyTheme = localStorage.getItem('finsight_theme') || 'dark';
  if (earlyTheme === 'light') {
    document.documentElement.classList.add('light-mode');
    if (document.body) document.body.classList.add('light-mode');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initThemeToggle);
  } else {
    initThemeToggle();
  }
})();

// Page Preloader Handler
(function() {
  function hidePreloader() {
    var preloader = document.getElementById('page-preloader');
    if (preloader && !preloader.classList.contains('fade-out')) {
      preloader.classList.add('fade-out');
      setTimeout(function() {
        preloader.style.display = 'none';
      }, 400);
    }
  }

  if (document.readyState === 'complete') {
    setTimeout(hidePreloader, 250);
  } else {
    window.addEventListener('load', function() {
      setTimeout(hidePreloader, 250);
    });
    // Fallback timer (2.5 seconds max)
    setTimeout(hidePreloader, 2500);
  }

  // Show preloader smoothly during internal page transitions
  document.addEventListener('click', function(e) {
    var anchor = e.target.closest('a');
    if (anchor && anchor.href && !anchor.target && !anchor.hasAttribute('download') && anchor.origin === window.location.origin) {
      var href = anchor.getAttribute('href') || '';
      if (!href.includes('#') && !anchor.classList.contains('no-preloader') && !href.startsWith('javascript:')) {
        var preloader = document.getElementById('page-preloader');
        if (preloader) {
          preloader.style.display = 'flex';
          preloader.classList.remove('fade-out');
        }
      }
    }
  });
})();

