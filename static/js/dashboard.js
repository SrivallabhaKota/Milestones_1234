document.addEventListener('DOMContentLoaded', function() {
  var state = {
    summary: null, profile: null, transactions: [],
    spending: null, insights: [], goalsData: null,
    monthlyTrend: null, aiInsights: null, budgets: []
  };

  var analyticsChartInst  = null;
  var goalStatusChartInst = null;
  var goalCatChartInst    = null;
  var goalTVSChartInst    = null;
  var goalTrendChartInst  = null;
  var monthlyTrendInst    = null;
  var isRefreshing = false;

  function fmt(n) {
    return (parseFloat(n) || 0).toLocaleString('en-IN', {maximumFractionDigits: 0});
  }
  function setEl(id, txt) {
    var el = document.getElementById(id);
    if (el) el.textContent = txt;
  }
  function setElHtml(id, html) {
    var el = document.getElementById(id);
    if (el) el.innerHTML = html;
  }
  function setElStyle(id, prop, val) {
    var el = document.getElementById(id);
    if (el) el.style[prop] = val;
  }
  function qsel(selector) { return document.querySelector(selector); }

  // ── KPI Cards ──────────────────────────────────────────────────
  function renderKPIs() {
    if (!state.summary) return;
    var s = state.summary;
    setEl('kpi-income', '\u20B9' + fmt(s.income.total));
    var iChg = s.income.change || 0;
    var iSub = document.getElementById('kpi-income-sub');
    if (iSub) {
      iSub.textContent = (iChg >= 0 ? '\u2191' : '\u2193') + ' ' + Math.abs(iChg) + '% vs last month';
      iSub.style.color = iChg >= 0 ? '#10B981' : '#EF4444';
    }
    setEl('kpi-expenses', '\u20B9' + fmt(s.expenses.total));
    var eChg = s.expenses.change || 0;
    var eSub = document.getElementById('kpi-expenses-sub');
    if (eSub) {
      eSub.textContent = (eChg >= 0 ? '\u2191' : '\u2193') + ' ' + Math.abs(eChg) + '% vs last month';
      eSub.style.color = eChg >= 0 ? '#EF4444' : '#10B981';
    }
    var inc = s.income.total || 0, exp = s.expenses.total || 0;
    var rate = inc > 0 ? Math.round((inc - exp) / inc * 100) : 0;
    var srEl = document.getElementById('kpi-savings-rate');
    if (srEl) {
      srEl.textContent = rate + '%';
      srEl.style.color = rate >= 20 ? '#10B981' : rate >= 5 ? '#F59E0B' : '#EF4444';
    }
    var subEl = document.getElementById('income-allocation-subtitle');
    if (subEl) subEl.textContent = 'How your \u20B9' + fmt(s.income.total) + ' income is split';
    var sdEl = document.getElementById('savings-diff-text');
    if (sdEl) sdEl.textContent = s.savings && s.savings.total > 0 ? 'Saved \u20B9' + fmt(s.savings.total) + ' this month' : 'Live financial breakdown';
  }

  function renderKPIBudget(budgets) {
    if (!budgets || budgets.length === 0) return;
    var totalLimit = budgets.reduce(function(a, b) { return a + (b.limit_amount || 0); }, 0);
    var totalSpent = budgets.reduce(function(a, b) { return a + (b.spent || 0); }, 0);
    var pct = totalLimit > 0 ? Math.round(totalSpent / totalLimit * 100) : 0;
    var el = document.getElementById('kpi-budget-pct');
    if (el) {
      el.textContent = pct + '%';
      el.style.color = pct >= 100 ? '#EF4444' : pct >= 80 ? '#F59E0B' : '#8B5CF6';
    }
    var sub = document.getElementById('kpi-budget-sub');
    if (sub) sub.textContent = '\u20B9' + fmt(totalSpent) + ' of \u20B9' + fmt(totalLimit);
  }

  function renderKPIGoals(goalsData) {
    if (!goalsData) return;
    var active = (goalsData.status_distribution && goalsData.status_distribution['Active']) || 0;
    setEl('kpi-goals', active);
    var total = Object.values(goalsData.status_distribution || {}).reduce(function(a, b) { return a + b; }, 0);
    setEl('kpi-goals-sub', total + ' total goals');
  }

  // ── Doughnut Chart ─────────────────────────────────────────────
  function renderAnalyticsChart() {
    if (!state.summary) return;
    var ctx = document.getElementById('analyticsChart');
    if (!ctx) return;
    if (analyticsChartInst) { analyticsChartInst.destroy(); analyticsChartInst = null; }
    var s = state.summary;
    var legend = qsel('.legend-list');
    if (legend) {
      legend.innerHTML = '';
      var segs = [
        {label:'Expenses',    amount: s.expenses.total,    pct: s.chart_segments.expenses,    color:'#EF4444'},
        {label:'Savings',     amount: s.savings.total,     pct: s.chart_segments.savings,     color:'#10B981'},
        {label:'Investments', amount: s.investments.total, pct: s.chart_segments.investments, color:'#6366F1'},
        {label:'Remaining',   amount: s.remaining.total,   pct: s.chart_segments.remaining,   color:'#F59E0B'}
      ];
      segs.forEach(function(item) {
        var row = document.createElement('div');
        row.className = 'legend-row';
        row.style.borderTop = '3px solid ' + item.color;
        row.innerHTML =
          '<div class="legend-label" style="color:' + item.color + '"><span>' + item.label + '</span></div>' +
          '<div class="legend-meta"><strong>\u20B9' + fmt(item.amount) + '</strong>' +
          '<span style="font-size:0.78rem;font-weight:600;color:#64748B;">(' + item.pct + '%)</span></div>';
        legend.appendChild(row);
      });
    }
    analyticsChartInst = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Expenses','Savings','Investments','Remaining'],
        datasets: [{
          data: [
            s.chart_segments.expenses || 0,
            s.chart_segments.savings  || 0,
            s.chart_segments.investments || 0,
            s.chart_segments.remaining   || 0
          ],
          backgroundColor: ['#EF4444','#10B981','#6366F1','#F59E0B'],
          borderWidth: 0, hoverOffset: 10
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '70%',
        plugins: {legend:{display:false}, tooltip:{enabled:true}}
      },
      plugins: [{
        id: 'centerText',
        beforeDraw: function(chart) {
          var c = chart.ctx, ca = chart.chartArea;
          if (!ca) return;
          var cx = ca.left + (ca.right - ca.left) / 2;
          var cy = ca.top  + (ca.bottom - ca.top)  / 2;
          c.save();
          c.font = '600 11px Inter'; c.fillStyle = '#94A3B8'; c.textAlign = 'center';
          c.fillText('Total Income', cx, cy - 8);
          c.font = '800 17px Inter'; c.fillStyle = '#0F172A';
          c.fillText('\u20B9' + fmt(s.income.total), cx, cy + 13);
          c.restore();
        }
      }]
    });
  }

  // ── Transactions ───────────────────────────────────────────────
  function renderTransactions() {
    var list = qsel('.transaction-list');
    if (!list) return;
    list.innerHTML = '';
    if (!state.transactions || state.transactions.length === 0) {
      list.innerHTML = '<div style="text-align:center;padding:24px 0;color:#94A3B8;font-size:0.88rem;">No recent transactions found</div>';
      return;
    }
    state.transactions.forEach(function(item) {
      var row = document.createElement('div');
      row.className = 'transaction-row';
      var clr  = item.type === 'income' ? 'green' : item.type === 'investment' ? 'purple' : 'orange';
      var sign = item.type === 'income' ? '+' : '-';
      var icon = item.type === 'income' ? '\ud83d\udcb0' : item.type === 'investment' ? '\ud83d\udcc8' : '\ud83d\uded2';
      row.innerHTML =
        '<div class="transaction-left">' +
          '<div class="transaction-icon ' + clr + '">' + icon + '</div>' +
          '<div><div class="transaction-title">' + (item.title || item.category) + '</div>' +
          '<div class="transaction-subtitle">' + (item.category || '') + '</div></div></div>' +
        '<div class="transaction-right">' +
          '<div class="amount ' + (item.type === 'income' ? 'positive' : 'negative') + '">' + sign + '\u20B9' + fmt(item.amount) + '</div>' +
          '<div class="date">' + (item.date || '') + '</div></div>';
      list.appendChild(row);
    });
  }

  // ── Insights ────────────────────────────────────────────────────
  function renderInsights() {
    var list = qsel('.insight-list');
    if (!list) return;
    list.innerHTML = '';
    if (!state.insights || state.insights.length === 0) {
      list.innerHTML = '<div style="text-align:center;padding:24px 0;color:#94A3B8;font-size:0.88rem;">No insights available yet</div>';
      return;
    }
    state.insights.forEach(function(item) {
      var row = document.createElement('div');
      row.className = 'insight-item';
      var pct = Math.min(100, Math.max(0, item.percentage || 0));
      row.innerHTML =
        '<div class="insight-row">' +
          '<div class="insight-left">' +
            '<div class="insight-icon" style="background:' + item.color + '1A;color:' + item.color + ';">\ud83d\udcca</div>' +
            '<div><div class="insight-title">' + item.title + '</div>' +
            '<div class="insight-desc">' + item.description + '</div></div></div>' +
          '<div class="insight-badge badge-on-track">' + item.status + '</div></div>' +
        '<div class="progress-bar"><span style="background:' + item.color + ';width:' + pct + '%"></span></div>';
      list.appendChild(row);
    });
  }

  // ── Monthly Trend Chart (Bar + Line) ──────────────────────────
  function renderMonthlyTrendChart() {
    if (!state.monthlyTrend) return;
    var ctx = document.getElementById('monthlyTrendChart');
    if (!ctx) return;
    if (monthlyTrendInst) { monthlyTrendInst.destroy(); monthlyTrendInst = null; }
    var d = state.monthlyTrend;
    monthlyTrendInst = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: d.labels,
        datasets: [
          {
            label: 'Income', data: d.income, type: 'bar',
            backgroundColor: 'rgba(59,130,246,0.78)', borderRadius: 8, borderSkipped: false, order: 2
          },
          {
            label: 'Expenses', data: d.expenses, type: 'bar',
            backgroundColor: 'rgba(239,68,68,0.78)', borderRadius: 8, borderSkipped: false, order: 2
          },
          {
            label: 'Budget Limit', data: d.budget, type: 'line',
            borderColor: '#F59E0B', borderWidth: 2.5, borderDash: [6,4],
            pointBackgroundColor: '#F59E0B', pointRadius: 4, tension: 0.4, fill: false, order: 1
          }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {legend:{display:false}, tooltip:{mode:'index',intersect:false}},
        scales: {
          y: {
            beginAtZero: true,
            grid: {color:'rgba(148,163,184,0.12)'},
            ticks: {callback: function(v){ return '\u20B9' + (v >= 1000 ? Math.round(v/1000) + 'k' : v); }}
          },
          x: {grid:{display:false}}
        }
      }
    });
  }

  // ── AI Insights ─────────────────────────────────────────────────
  function renderAIInsights() {
    var grid = document.getElementById('ai-insights-grid');
    if (!grid || !state.aiInsights) return;
    var ins = state.aiInsights.insights || [];
    if (ins.length === 0) {
      grid.innerHTML = '<div class="ai-card"><div class="ai-card-top"><span class="ai-card-icon">\ud83d\ude80</span><span class="ai-card-badge">Get Started</span></div><div class="ai-card-title">Start Tracking</div><div class="ai-card-text">Add income and expenses to unlock AI analysis.</div></div>';
      return;
    }
    grid.innerHTML = '';
    ins.forEach(function(item, i) {
      var card = document.createElement('div');
      card.className = 'ai-card';
      card.style.animationDelay = (i * 0.08) + 's';
      card.innerHTML =
        '<div class="ai-card-top"><span class="ai-card-icon">' + (item.icon || '\ud83d\udcca') + '</span>' +
        '<span class="ai-card-badge">' + item.badge + '</span></div>' +
        '<div class="ai-card-title">' + item.title + '</div>' +
        '<div class="ai-card-text">' + item.text + '</div>';
      grid.appendChild(card);
    });
  }

  // ── Budget Tracker ───────────────────────────────────────────────
  function renderBudgetTracker() {
    var grid = document.getElementById('budget-tracker-grid');
    if (!grid) return;
    if (!state.budgets || state.budgets.length === 0) {
      grid.innerHTML = '<div style="color:#94A3B8;font-size:0.85rem;padding:20px 0;grid-column:1/-1;">No budgets found. <a href="/add-budget" style="color:#6366F1;font-weight:600;">Create one \u2192</a></div>';
      return;
    }
    grid.innerHTML = '';
    var months = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    state.budgets.slice(0, 8).forEach(function(b, i) {
      var card = document.createElement('div');
      card.className = 'budget-tracker-card';
      card.style.animationDelay = (i * 0.07) + 's';
      var pct = Math.min(b.percent_used || 0, 100);
      var st  = b.status || 'ok';
      var goalHtml = b.goal_name
        ? '<span class="btc-goal-link">\ud83c\udfaf ' + b.goal_name + '</span>'
        : '<span class="btc-no-goal">No goal linked</span>';
      card.innerHTML =
        '<div class="btc-top"><span class="btc-cat">' + b.category + '</span>' + goalHtml + '</div>' +
        '<div class="btc-amounts"><span>Spent: <strong>\u20B9' + fmt(b.spent) + '</strong></span>' +
        '<span>Limit: <strong>\u20B9' + fmt(b.limit_amount) + '</strong></span></div>' +
        '<div class="btc-bar-wrap"><div class="btc-bar ' + st + '" style="width:' + pct + '%"></div></div>' +
        '<div class="btc-footer"><span class="btc-pct ' + st + '">' + (b.percent_used || 0) + '% used</span>' +
        '<span class="btc-month">' + (months[b.month] || '') + ' ' + b.year + '</span></div>';
      grid.appendChild(card);
    });
  }

  // ── Goals Charts ──────────────────────────────────────────────
  function renderGoalsCharts() {
    if (!state.goalsData) return;
    var g = state.goalsData;

    // Status doughnut
    var ctx1 = document.getElementById('goalStatusChart');
    if (ctx1) {
      if (goalStatusChartInst) { goalStatusChartInst.destroy(); goalStatusChartInst = null; }
      goalStatusChartInst = new Chart(ctx1, {
        type: 'doughnut',
        data: {
          labels: ['Active','Completed','On Hold'],
          datasets: [{
            data: [g.status_distribution.Active || 0, g.status_distribution.Completed || 0, g.status_distribution['On Hold'] || 0],
            backgroundColor: ['#6366F1','#10B981','#F59E0B'], borderWidth: 0, hoverOffset: 6
          }]
        },
        options: {responsive:true,maintainAspectRatio:false,cutout:'65%',plugins:{legend:{position:'bottom',labels:{font:{size:11},padding:10}}}}
      });
    }

    // Category pie
    var ctx2 = document.getElementById('goalCategoryChart');
    if (ctx2) {
      if (goalCatChartInst) { goalCatChartInst.destroy(); goalCatChartInst = null; }
      var cats   = g.category_distribution || {};
      var cLabels = Object.keys(cats);
      var cVals   = Object.values(cats);
      var colors  = ['#6366F1','#10B981','#F59E0B','#EF4444','#8B5CF6','#3B82F6','#F97316','#EC4899'];
      goalCatChartInst = new Chart(ctx2, {
        type: 'pie',
        data: {labels:cLabels, datasets:[{data:cVals, backgroundColor:colors.slice(0,cLabels.length), borderWidth:0, hoverOffset:6}]},
        options: {responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'bottom',labels:{font:{size:10},padding:8}}}}
      });
    }

    // Target vs Saved bar
    var ctx3 = document.getElementById('goalTargetVsSavedChart');
    if (ctx3 && g.target_vs_saved && g.target_vs_saved.labels && g.target_vs_saved.labels.length > 0) {
      if (goalTVSChartInst) { goalTVSChartInst.destroy(); goalTVSChartInst = null; }
      goalTVSChartInst = new Chart(ctx3, {
        type: 'bar',
        data: {
          labels: g.target_vs_saved.labels,
          datasets: [
            {label:'Target', data:g.target_vs_saved.target, backgroundColor:'rgba(99,102,241,0.75)', borderRadius:6},
            {label:'Saved',  data:g.target_vs_saved.saved,  backgroundColor:'rgba(16,185,129,0.75)', borderRadius:6}
          ]
        },
        options: {
          responsive:true, maintainAspectRatio:false,
          plugins:{legend:{position:'top',labels:{font:{size:11}}}},
          scales:{y:{beginAtZero:true,ticks:{callback:function(v){return '\u20B9'+(v>=1000?Math.round(v/1000)+'k':v);}}},x:{ticks:{maxRotation:30}}}
        }
      });
    }

    // Monthly savings trend line
    var ctx4 = document.getElementById('goalTrendChart');
    if (ctx4 && g.monthly_trend && g.monthly_trend.length > 0) {
      if (goalTrendChartInst) { goalTrendChartInst.destroy(); goalTrendChartInst = null; }
      goalTrendChartInst = new Chart(ctx4, {
        type: 'line',
        data: {
          labels: g.monthly_trend.map(function(r){ return r.label; }),
          datasets: [{
            label: 'Savings',
            data: g.monthly_trend.map(function(r){ return r.amount; }),
            borderColor: '#6366F1', borderWidth: 3,
            backgroundColor: function(context) {
              var chart = context.chart, ca = chart.chartArea;
              if (!ca) return 'rgba(99,102,241,0.15)';
              var grad = chart.ctx.createLinearGradient(0, ca.top, 0, ca.bottom);
              grad.addColorStop(0, 'rgba(99,102,241,0.3)');
              grad.addColorStop(1, 'rgba(99,102,241,0.02)');
              return grad;
            },
            fill: true, tension: 0.4, pointRadius: 5, pointBackgroundColor: '#6366F1'
          }]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: {legend:{display:false}},
          scales: {y:{beginAtZero:true,ticks:{callback:function(v){return '\u20B9'+(v>=1000?Math.round(v/1000)+'k':v);}}},x:{grid:{display:false}}}
        }
      });
    }

    // Recent Goals list
    var goalsList = document.getElementById('recent-goals-list');
    if (goalsList && g.recent_goals && g.recent_goals.length > 0) {
      goalsList.innerHTML = '';
      g.recent_goals.forEach(function(goal) {
        var row = document.createElement('div');
        row.className = 'transaction-row';
        var pct = goal.progress_percentage || 0;
        var clr = pct >= 100 ? '#10B981' : pct >= 60 ? '#6366F1' : '#F59E0B';
        row.innerHTML =
          '<div class="transaction-left">' +
            '<div class="transaction-icon purple">\ud83c\udfaf</div>' +
            '<div><div class="transaction-title">' + goal.goal_name + '</div>' +
            '<div class="transaction-subtitle">' + goal.category + ' &bull; ' + pct + '% done</div></div></div>' +
          '<div class="transaction-right">' +
            '<div class="amount" style="color:' + clr + ';font-size:0.82rem;">\u20B9' + fmt(goal.current_amount || 0) + '</div>' +
            '<div class="date">' + (goal.smart_status || '') + '</div></div>';
        goalsList.appendChild(row);
      });
    } else if (goalsList) {
      goalsList.innerHTML = '<div style="text-align:center;padding:20px;color:#94A3B8;font-size:0.85rem;">No goals found. <a href="/goals" style="color:#6366F1;">Create one \u2192</a></div>';
    }
  }

  // ── Fetch ─────────────────────────────────────────────────────
  function fetchJson(url) {
    return fetch(url).then(function(r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  }

  // ── Bootstrap Dashboard ───────────────────────────────────────
  function bootstrapDashboard(isRefresh) {
    if (isRefreshing) return;
    isRefreshing = true;

    Promise.all([
      fetchJson('/api/dashboard-summary').catch(function(){ return null; }),
      fetchJson('/api/recent-transactions').catch(function(){ return []; }),
      fetchJson('/api/monthly-spending').catch(function(){ return null; }),
      fetchJson('/api/insights').catch(function(){ return []; }),
      fetchJson('/api/dashboard-goals-data').catch(function(){ return null; }),
      fetchJson('/api/monthly-trend').catch(function(){ return null; }),
      fetchJson('/api/spending-analysis').catch(function(){ return null; }),
      fetchJson('/api/budget-with-goals').catch(function(){ return []; })
    ]).then(function(results) {
      state.summary      = results[0];
      state.transactions = results[1];
      state.spending     = results[2];
      state.insights     = results[3];
      state.goalsData    = results[4];
      state.monthlyTrend = results[5];
      state.aiInsights   = results[6];
      state.budgets      = results[7];

      if (state.summary)    { renderKPIs(); renderAnalyticsChart(); }
      renderTransactions();
      renderInsights();
      if (state.monthlyTrend) renderMonthlyTrendChart();
      if (state.aiInsights)   renderAIInsights();
      if (state.budgets)      { renderBudgetTracker(); renderKPIBudget(state.budgets); }
      if (state.goalsData)    { renderGoalsCharts(); renderKPIGoals(state.goalsData); }

      if (isRefresh) {
        document.querySelectorAll('.kpi-card').forEach(function(c) {
          c.classList.add('refresh-flash');
          setTimeout(function() { c.classList.remove('refresh-flash'); }, 800);
        });
      }
    }).catch(function(e) {
      console.error('Dashboard error:', e);
    }).finally(function() {
      isRefreshing = false;
    });
  }

  // ── Nav Active State ─────────────────────────────────────────
  (function() {
    var currentPath = window.location.pathname;
    document.querySelectorAll('.nav-item').forEach(function(link) {
      if (link.getAttribute('href') === currentPath) {
        link.classList.add('active');
      }
    });
  })();

  // Initial load + auto-refresh every 60 seconds (NOT every 1 second — no flicker)
  bootstrapDashboard(false);
  setInterval(function() { bootstrapDashboard(true); }, 60000);
});
