/* ============================================================
   FinSight – script.js
   Cursor Ring Only (no dot, no trail, no particles)
   ============================================================ */

'use strict';


// ── Flash Alert Auto-dismiss ───────────────────────────────
(function initAlerts() {
  document.querySelectorAll('.alert-close').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var alert = btn.closest('.alert-custom');
      if (alert) alert.remove();
    });
  });
  // Auto-dismiss after 5 seconds
  setTimeout(function() {
    document.querySelectorAll('.alert-custom').forEach(function(a) {
      a.style.opacity = '0';
      a.style.transition = 'opacity 0.5s ease';
      setTimeout(function() { a.remove(); }, 500);
    });
  }, 5000);
})();


// ── Password Toggle ────────────────────────────────────────
(function initPasswordToggle() {
  function setupToggle(toggleId, inputId) {
    var btn = document.getElementById(toggleId);
    var inp = document.getElementById(inputId);
    if (!btn || !inp) return;
    btn.addEventListener('click', function() {
      var isPass = inp.type === 'password';
      inp.type = isPass ? 'text' : 'password';
      var icon = btn.querySelector('i');
      if (icon) {
        icon.className = isPass ? 'bi bi-eye-slash-fill' : 'bi bi-eye-fill';
      }
    });
  }
  setupToggle('toggle-password', 'password');
  setupToggle('toggle-confirm',  'confirm_password');
})();


// ── Password Strength Meter ────────────────────────────────
(function initPasswordStrength() {
  var pwInput = document.getElementById('password');
  if (!pwInput) return;

  var bars   = [1,2,3,4].map(function(n){ return document.getElementById('sbar-' + n); });
  var label  = document.getElementById('strength-label');
  var rules  = {
    len:     document.getElementById('rule-len'),
    upper:   document.getElementById('rule-upper'),
    lower:   document.getElementById('rule-lower'),
    number:  document.getElementById('rule-number'),
    special: document.getElementById('rule-special')
  };

  pwInput.addEventListener('input', function() {
    var val = pwInput.value;
    var score = 0;

    var checks = {
      len:     val.length >= 8,
      upper:   /[A-Z]/.test(val),
      lower:   /[a-z]/.test(val),
      number:  /\d/.test(val),
      special: /[!@#$%^&*(),.?":{}|<>_\-\[\]\/\\]/.test(val)
    };

    Object.keys(checks).forEach(function(key) {
      var el = rules[key];
      if (!el) return;
      var icon = el.querySelector('i');
      if (checks[key]) {
        el.classList.add('met');
        if (icon) icon.className = 'bi bi-check-circle-fill';
        score++;
      } else {
        el.classList.remove('met');
        if (icon) icon.className = 'bi bi-circle';
      }
    });

    // Strength bars
    var classes = ['active-weak','active-fair','active-good','active-strong'];
    bars.forEach(function(b, i) {
      if (!b) return;
      b.className = 'strength-bar';
      if (i < score) b.classList.add(classes[Math.min(score-1, 3)]);
    });

    if (label) {
      var labels = ['','Weak','Fair','Good','Strong','Very Strong'];
      label.textContent = val.length ? labels[Math.min(score, 5)] : '';
    }
  });
})();


// ── Confirm Password Match ─────────────────────────────────
(function initConfirmMatch() {
  var pw  = document.getElementById('password');
  var cpw = document.getElementById('confirm_password');
  var msg = document.getElementById('confirm-validation-msg');
  if (!pw || !cpw || !msg) return;

  function check() {
    if (!cpw.value) { msg.textContent = ''; cpw.classList.remove('is-valid','is-invalid'); return; }
    if (cpw.value === pw.value) {
      msg.className = 'validation-msg valid';
      msg.textContent = '✓ Passwords match';
      cpw.classList.add('is-valid'); cpw.classList.remove('is-invalid');
    } else {
      msg.className = 'validation-msg invalid';
      msg.textContent = '✗ Passwords do not match';
      cpw.classList.add('is-invalid'); cpw.classList.remove('is-valid');
    }
  }
  cpw.addEventListener('input', check);
  pw.addEventListener('input', check);
})();


// ── Email Validation ───────────────────────────────────────
(function initEmailValidation() {
  var emailInput = document.getElementById('email');
  var emailMsg   = document.getElementById('email-validation-msg');
  if (!emailInput || !emailMsg) return;

  emailInput.addEventListener('blur', function() {
    var val = emailInput.value.trim();
    if (!val) { emailMsg.textContent = ''; return; }
    var valid = /^[\w\.+\-]+@[\w\-]+\.[a-zA-Z]{2,}$/.test(val);
    if (valid) {
      emailMsg.className = 'validation-msg valid';
      emailMsg.textContent = '✓ Valid email address';
      emailInput.classList.add('is-valid'); emailInput.classList.remove('is-invalid');
    } else {
      emailMsg.className = 'validation-msg invalid';
      emailMsg.textContent = '✗ Invalid email format';
      emailInput.classList.add('is-invalid'); emailInput.classList.remove('is-valid');
    }
  });
})();


// ── Home Page Mobile Nav Toggle ────────────────────────────
(function initHomeNav() {
  var toggler    = document.getElementById('home-nav-toggler');
  var mobileMenu = document.getElementById('home-nav-mobile');
  if (!toggler || !mobileMenu) return;

  toggler.addEventListener('click', function() {
    var isOpen = mobileMenu.classList.toggle('open');
    toggler.setAttribute('aria-expanded', isOpen.toString());
    mobileMenu.setAttribute('aria-hidden', (!isOpen).toString());
  });

  mobileMenu.querySelectorAll('.home-nav-mobile-link').forEach(function(link) {
    link.addEventListener('click', function() {
      mobileMenu.classList.remove('open');
      toggler.setAttribute('aria-expanded', 'false');
      mobileMenu.setAttribute('aria-hidden', 'true');
    });
  });
})();
