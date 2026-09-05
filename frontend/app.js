// State Management
let globalState = {
  customers: [],
  selectedCustomerId: null,
  transactions: [],
  report: null,
  config: []
};

// Router
const views = {
  'investigation': initInvestigation,
  'baseline': initBaseline,
  'config': initConfig,
  'audit': initAudit
};

async function loadView(viewName) {
  try {
    const res = await fetch('views/' + viewName + '.html');
    if (!res.ok) throw new Error("Failed to load view");
    const html = await res.text();
    document.getElementById('app-root').innerHTML = html;
    
    document.querySelectorAll('#sidebar-nav .nav-link').forEach(function(link) {
      if (link.dataset.path === viewName) {
        link.className = "nav-link flex items-center gap-3 px-3 py-2.5 rounded-lg bg-brand-blue-subtle text-primary font-semibold text-sm transition-colors";
      } else {
        link.className = "nav-link flex items-center gap-3 px-3 py-2.5 rounded-lg font-medium text-sm text-text-secondary hover:bg-surface-subtle hover:text-text-primary transition-colors";
      }
    });

    if (views[viewName]) {
      views[viewName]();
    }
  } catch (err) {
    console.error(err);
    document.getElementById('app-root').innerHTML = '<div class="p-8 text-red-500">Error loading view: ' + viewName + '</div>';
  }
}

function handleRoute() {
  var hash = window.location.hash.replace('#/', '');
  if (!hash || !views[hash]) hash = 'investigation';
  loadView(hash);
}

window.addEventListener('hashchange', handleRoute);

// API Helpers
async function fetchCustomers() {
  if (globalState.customers.length === 0) {
    const res = await fetch('/api/customers');
    globalState.customers = await res.json();
  }
  return globalState.customers;
}

async function fetchTransactions(customerId) {
  const res = await fetch('/api/customers/' + customerId + '/transactions');
  globalState.transactions = await res.json();
  return globalState.transactions;
}

async function runInvestigation(customerId) {
  const res = await fetch('/api/customers/' + customerId + '/investigate', { method: 'POST' });
  globalState.report = await res.json();
  return globalState.report;
}

// Initializers
function initInvestigation() {
  const select = document.getElementById('customer-select');
  const meta = document.getElementById('customer-meta');
  const btn = document.getElementById('investigate-btn');
  const container = document.getElementById('investigation-results-container');
  const list = document.getElementById('rule-violations-list');
  const tbody = document.getElementById('transactions-list-tbody');
  
  if (!select) return;

  // Populate dropdown
  var optionsHtml = '';
  globalState.customers.forEach(function(c) {
    var sel = (globalState.selectedCustomerId == c.customer_id) ? 'selected' : '';
    optionsHtml += '<option value="' + c.customer_id + '" ' + sel + '>' + c.full_name + '</option>';
  });
  select.innerHTML = optionsHtml;

  var updateMeta = function() {
    var c = globalState.customers.find(function(c) { return c.customer_id == select.value; });
    if(c) meta.textContent = 'Account opened: ' + new Date(c.account_opened_date).toLocaleDateString();
    globalState.selectedCustomerId = select.value;
    container.classList.add('hidden');
    loadTransactions();
  };

  select.addEventListener('change', updateMeta);
  updateMeta();

  async function loadTransactions() {
    tbody.innerHTML = '<tr><td colspan="6" class="py-4 text-center">Loading...</td></tr>';
    var txns = await fetchTransactions(globalState.selectedCustomerId);
    renderTxns(txns, new Set());
  }

  function renderTxns(txns, flaggedIds) {
    var html = '';
    txns.forEach(function(t) {
      var isFlagged = flaggedIds.has(t.txn_id);
      var statusBadge = isFlagged
        ? '<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-risk-critical-bg text-risk-critical"><span class="w-1.5 h-1.5 rounded-full bg-risk-critical"></span> Flagged</span>'
        : '<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-status-safe-bg text-status-safe"><span class="w-1.5 h-1.5 rounded-full bg-status-safe"></span> Cleared</span>';
      var rowClass = isFlagged ? 'bg-risk-warning-bg/10' : '';
      var amt = parseFloat(t.amount).toLocaleString('en-IN', {minimumFractionDigits: 2});
      html += '<tr class="hover:bg-surface-subtle/50 transition-colors ' + rowClass + '">'
        + '<td class="py-3.5">' + statusBadge + '</td>'
        + '<td class="py-3.5 font-mono font-medium text-brand-navy">TX-' + t.txn_id + '</td>'
        + '<td class="py-3.5">' + t.txn_date + ' ' + t.txn_time + '</td>'
        + '<td class="py-3.5 text-brand-navy font-medium">' + (t.payee_name || t.description || '-') + '</td>'
        + '<td class="py-3.5 font-mono font-bold text-brand-navy text-right">\u20B9' + amt + '</td>'
        + '<td class="py-3.5 font-mono text-text-tertiary text-right">' + t.channel + '</td>'
        + '</tr>';
    });
    tbody.innerHTML = html;
  }

  btn.addEventListener('click', async function() {
    btn.innerHTML = '<span class="material-symbols-outlined text-[16px] animate-spin">sync</span><span>Running...</span>';
    btn.disabled = true;
    
    try {
      var report = await runInvestigation(globalState.selectedCustomerId);
      
      var badge = document.getElementById('investigation-status-badge');
      badge.classList.remove('hidden');
      if (report.overall_verdict === 'no_concerns') {
        badge.className = "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-status-safe-bg text-status-safe border border-status-safe-border";
        badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-status-safe"></span>No Concerns';
        list.innerHTML = '<div class="p-4 text-sm text-status-safe bg-status-safe-bg rounded">All transactions appear normal.</div>';
      } else {
        badge.className = "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-risk-warning-bg text-risk-warning border border-amber-200";
        badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-risk-warning"></span>Review Recommended';
        
        var findingsHtml = '';
        report.findings.forEach(function(f) {
          var txnIds = f.transactions.map(function(t) { return '#TX-' + t.txn_id; }).join(', ');
          var dotClass = f.severity === 'high' ? 'bg-risk-critical' : 'bg-risk-warning';
          findingsHtml += '<div class="p-4 rounded-lg border border-border-subtle hover:border-border-strong transition-colors flex flex-col sm:flex-row justify-between gap-3 bg-surface-default">'
            + '<div>'
            + '<div class="flex items-center gap-2">'
            + '<span class="w-2 h-2 rounded-full ' + dotClass + ' shrink-0"></span>'
            + '<span class="text-sm font-semibold text-brand-navy">' + f.rule_code + '</span>'
            + '<span class="font-mono text-xs text-text-tertiary">' + txnIds + '</span>'
            + '</div>'
            + '<p class="text-xs text-text-secondary mt-1 pl-4">' + f.summary + '</p>'
            + '</div></div>';
        });
        list.innerHTML = findingsHtml;
      }

      var flaggedIds = new Set();
      report.findings.forEach(function(f) {
        f.transactions.forEach(function(t) { flaggedIds.add(t.txn_id); });
      });
      renderTxns(globalState.transactions, flaggedIds);

      container.classList.remove('hidden');
    } catch(err) {
      alert("Error running investigation.");
    } finally {
      btn.innerHTML = '<span class="material-symbols-outlined text-[16px]">sync</span><span>Run Investigation</span>';
      btn.disabled = false;
    }
  });
}

function initBaseline() {
  var nameEl = document.getElementById('baseline-customer-name');
  if (nameEl && globalState.selectedCustomerId) {
    var c = globalState.customers.find(function(c) { return c.customer_id == globalState.selectedCustomerId; });
    if (c) nameEl.textContent = c.full_name;
  }

  var chartCanvas = document.getElementById('baselineChart');
  var placeholder = document.getElementById('baseline-placeholder');

  if (!globalState.report || !globalState.transactions.length) {
    chartCanvas.classList.add('hidden');
    placeholder.classList.remove('hidden');
    return;
  }

  chartCanvas.classList.remove('hidden');
  placeholder.classList.add('hidden');

  var b = globalState.report.baseline_summary;
  document.getElementById('stat-avg').textContent = '\u20B9' + parseFloat(b.avg_amount).toLocaleString('en-IN', {minimumFractionDigits:2});
  document.getElementById('stat-stddev').textContent = '\u00B1\u20B9' + parseFloat(b.stddev_amount).toLocaleString('en-IN', {minimumFractionDigits:2});
  document.getElementById('stat-hours').textContent = b.typical_hours;
  document.getElementById('stat-channels').textContent = b.typical_channels.join(', ') || 'N/A';

  // Render chart
  if (window.currentChart) window.currentChart.destroy();
  
  var citedIds = new Set();
  globalState.report.findings.forEach(function(f) {
    f.transactions.forEach(function(t) { citedIds.add(t.txn_id); });
  });
  
  var scatterData = globalState.transactions.map(function(t) {
    var d = new Date(t.txn_date + 'T' + t.txn_time);
    return {
      x: d.getTime(),
      y: parseFloat(t.amount),
      isCited: citedIds.has(t.txn_id)
    };
  });

  window.currentChart = new Chart(chartCanvas, {
    type: 'scatter',
    data: {
      datasets: [
        {
          label: 'Routine',
          data: scatterData.filter(function(d) { return !d.isCited; }),
          backgroundColor: '#3b82f6',
          pointRadius: 4
        },
        {
          label: 'Flagged',
          data: scatterData.filter(function(d) { return d.isCited; }),
          backgroundColor: '#ef4444',
          pointRadius: 6,
          pointHoverRadius: 8
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#64748b' } },
        tooltip: {
          callbacks: {
            label: function(ctx) { return '\u20B9' + ctx.raw.y.toLocaleString() + ' on ' + new Date(ctx.raw.x).toLocaleString(); }
          }
        }
      },
      scales: {
        x: {
          type: 'linear',
          position: 'bottom',
          ticks: { color: '#64748b', callback: function(value) { return new Date(value).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}); } },
          grid: { color: '#e2e8f0' }
        },
        y: { 
          ticks: { color: '#64748b', callback: function(value) { return '\u20B9' + value; } },
          grid: { color: '#e2e8f0' }
        }
      }
    }
  });
}

async function initConfig() {
  var slider = document.getElementById('slider-large-txn');
  var label = document.getElementById('label-k-val');
  var saveBtn = document.getElementById('btn-save');
  var dryRunBtn = document.getElementById('btn-dry-run');
  var toast = document.getElementById('save-toast');
  var toastClose = document.getElementById('toast-close');

  var inputs = {
    'LARGE_TXN_STDDEV_K': slider,
    'LARGE_TXN_ABS_FLOOR': document.getElementById('input-floor-amount'),
    'NEW_PAYEE_WINDOW_DAYS': document.getElementById('input-payee-window'),
    'NEW_PAYEE_BURST_COUNT': document.getElementById('input-burst-count'),
    'NEW_PAYEE_BURST_WINDOW_HOURS': document.getElementById('input-spend-mult'),
    'ODD_HOURS_BUFFER': document.getElementById('input-buffer-mins')
  };

  // Load current config
  try {
    var res = await fetch('/api/config');
    var configData = await res.json();
    globalState.config = configData;
    
    configData.forEach(function(c) {
      if (inputs[c.config_key] && c.config_value) {
        inputs[c.config_key].value = c.config_value;
      }
    });

    if (slider && label) {
      label.textContent = parseFloat(slider.value).toFixed(1) + '\u03C3';
    }
  } catch (err) {
    console.error("Failed to load config", err);
  }

  // Event Listeners
  if (slider && label) {
    slider.addEventListener('input', function(e) {
      label.textContent = parseFloat(e.target.value).toFixed(1) + '\u03C3';
    });
  }

  if (toastClose && toast) {
    toastClose.addEventListener('click', function() { toast.classList.add('hidden'); });
  }

  if (saveBtn) {
    saveBtn.addEventListener('click', async function() {
      var prev = saveBtn.innerHTML;
      saveBtn.innerHTML = '<span class="material-symbols-outlined text-[16px] animate-spin">refresh</span><span>Saving...</span>';
      
      var updates = {};
      for (var key in inputs) {
        if (inputs[key]) updates[key] = inputs[key].value;
      }

      try {
        await fetch('/api/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(updates)
        });
        if (toast) {
          toast.classList.remove('hidden');
          setTimeout(function() { toast.classList.add('hidden'); }, 3500);
        }
      } catch (err) {
        alert("Failed to save configuration");
      } finally {
        saveBtn.innerHTML = prev;
      }
    });
  }

  if (dryRunBtn) {
    dryRunBtn.addEventListener('click', function() {
      var prev = dryRunBtn.innerHTML;
      dryRunBtn.innerHTML = '<span class="material-symbols-outlined text-[16px] animate-spin">refresh</span><span>Simulating...</span>';
      setTimeout(function() {
        dryRunBtn.innerHTML = prev;
      }, 1500);
    });
  }
}

function initAudit() {
  var nameEl1 = document.getElementById('audit-customer-name');
  var nameEl2 = document.getElementById('audit-entity-name');
  
  if (globalState.selectedCustomerId && nameEl1 && nameEl2) {
    var c = globalState.customers.find(function(c) { return c.customer_id == globalState.selectedCustomerId; });
    if (c) {
      nameEl1.textContent = c.full_name;
      nameEl2.textContent = c.full_name;
    }
  }

  var avgEl = document.getElementById('audit-stat-avg');
  if (avgEl && globalState.report) {
    avgEl.textContent = '\u20B9' + parseFloat(globalState.report.baseline_summary.avg_amount).toLocaleString('en-IN', {minimumFractionDigits:2});
  }

  // PDF Export
  function showToast(title, message) {
    var toast = document.getElementById('toastNotification');
    var toastTitle = document.getElementById('toastTitle');
    var toastMessage = document.getElementById('toastMessage');
    if (!toast) return;

    toastTitle.textContent = title;
    toastMessage.textContent = message;

    toast.classList.remove('hidden');
    toast.classList.remove('translate-y-2');

    setTimeout(function() {
      toast.classList.add('translate-y-2');
      setTimeout(function() { toast.classList.add('hidden'); }, 300);
    }, 3000);
  }

  var downloadPdfBtn = document.getElementById('downloadPdfBtn');
  if (downloadPdfBtn) {
    downloadPdfBtn.addEventListener('click', function() {
      window.print();
      showToast('SAR PDF Downloaded', 'Filing package successfully exported.');
    });
  }
}

// Bootstrap
async function bootstrap() {
  await fetchCustomers();
  if (globalState.customers.length > 0) {
    globalState.selectedCustomerId = globalState.customers[0].customer_id;
  }
  handleRoute();
}

bootstrap();
