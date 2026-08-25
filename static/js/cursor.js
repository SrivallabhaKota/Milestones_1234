/**
 * cursor.js — Premium animated cursor for FinSight
 * Adds a glowing dot + ring cursor with trail effect.
 * Theme color is set via body class (theme-dash, theme-income, etc.)
 */
(function () {
  // Restore sidebar state immediately to prevent layout shifts
  const savedState = localStorage.getItem('sidebarState');
  const sidebarEl = document.getElementById('sidebar');
  if (savedState === 'open') {
    document.body.classList.add('sidebar-open');
    if (sidebarEl) sidebarEl.classList.add('open');
  } else {
    document.body.classList.remove('sidebar-open');
    if (sidebarEl) sidebarEl.classList.remove('open');
  }

  const dot  = document.getElementById('cursor-dot');
  const ring = document.getElementById('cursor-ring');
  if (!dot || !ring) return;

  let mouseX = -100, mouseY = -100;
  let ringX  = -100, ringY  = -100;
  let rafId;

  // Determine trail color from body theme class
  function getTrailColor() {
    const body = document.body;
    if (body.classList.contains('theme-income'))  return '#10B981';
    if (body.classList.contains('theme-expense')) return '#F97316';
    if (body.classList.contains('theme-budget'))  return '#8B5CF6';
    if (body.classList.contains('theme-invest'))  return '#6366F1';
    return '#2563EB'; // default: blue (dashboard)
  }

  // Move dot instantly, ring follows with easing
  document.addEventListener('mousemove', (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;

    // Instant dot
    dot.style.left = mouseX + 'px';
    dot.style.top  = mouseY + 'px';

    // Spawn trail particle
    spawnTrail(mouseX, mouseY);
  });

  // Smooth ring follow via RAF
  function animateRing() {
    const ease = 0.13;
    ringX += (mouseX - ringX) * ease;
    ringY += (mouseY - ringY) * ease;
    ring.style.left = ringX + 'px';
    ring.style.top  = ringY + 'px';
    rafId = requestAnimationFrame(animateRing);
  }
  animateRing();

  // Hover effects
  const interactiveSelectors = 'a, button, input, select, textarea, label, [role="button"], .nav-item, .quick-nav-item, .stat-card, .panel, .page-submit-btn, .sidebar-refresh-btn';
  document.addEventListener('mouseover', (e) => {
    if (e.target.closest(interactiveSelectors)) {
      document.body.classList.add('cursor-hover');
    }
  });
  document.addEventListener('mouseout', (e) => {
    if (e.target.closest(interactiveSelectors)) {
      document.body.classList.remove('cursor-hover');
    }
  });

  // Click effect
  document.addEventListener('mousedown', () => {
    document.body.classList.add('cursor-click');
    document.body.classList.remove('cursor-hover');
  });
  document.addEventListener('mouseup', () => {
    document.body.classList.remove('cursor-click');
  });

  // Hide cursor when leaving window
  document.addEventListener('mouseleave', () => {
    dot.style.opacity  = '0';
    ring.style.opacity = '0';
  });
  document.addEventListener('mouseenter', () => {
    dot.style.opacity  = '1';
    ring.style.opacity = '1';
  });

  // Trail particles
  let lastTrail = 0;
  function spawnTrail(x, y) {
    const now = Date.now();
    if (now - lastTrail < 40) return; // throttle: 1 trail per 40ms
    lastTrail = now;

    const particle = document.createElement('div');
    particle.className = 'cursor-trail';
    particle.style.left = x + 'px';
    particle.style.top  = y + 'px';
    particle.style.background = getTrailColor();
    document.body.appendChild(particle);

    setTimeout(() => {
      if (particle.parentNode) particle.parentNode.removeChild(particle);
    }, 650);
  }

  // Global sidebar toggle handler for floating hamburger menu
  function initSidebarToggle() {
    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('sidebar-toggle-btn');
    if (toggleBtn && sidebar) {
      // Restore sidebar state from localStorage
      const savedState = localStorage.getItem('sidebarState');
      if (savedState === 'open') {
        sidebar.classList.add('open');
        document.body.classList.add('sidebar-open');
      } else {
        sidebar.classList.remove('open');
        document.body.classList.remove('sidebar-open');
      }

      toggleBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = sidebar.classList.toggle('open');
        document.body.classList.toggle('sidebar-open');
        // Persist state
        localStorage.setItem('sidebarState', isOpen ? 'open' : 'closed');
      });
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSidebarToggle);
  } else {
    initSidebarToggle();
  }
})();
