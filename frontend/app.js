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
      const icon = link.querySelector('.material-symbols-rounded');
      if (link.dataset.path === viewName) {
        link.className = "nav-link group flex items-center gap-3 px-4 py-2.5 rounded-xl font-semibold text-primary bg-primary-subtle shadow-sm transition-all duration-200 ease-out";
        if (icon) icon.className = "material-symbols-rounded text-[20px] text-primary transition-colors";
      } else {
        link.className = "nav-link group flex items-center gap-3 px-4 py-2.5 rounded-xl font-medium text-sm text-text-secondary hover:bg-surface-subtle hover:text-text-primary transition-all duration-200 ease-out";
        if (icon) icon.className = "material-symbols-rounded text-[20px] text-text-tertiary group-hover:text-primary transition-colors";
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

  var searchInput = document.getElementById('search-input');
  if (searchInput) {
    searchInput.addEventListener('input', function(e) {
      var query = e.target.value.toLowerCase();
      var rows = document.querySelectorAll('#transactions-list-tbody tr');
      rows.forEach(function(row) {
        var text = row.textContent.toLowerCase();
        // Skip hidden by filter
        if (row.dataset.filtered === 'true') return;
        row.style.display = text.includes(query) ? '' : 'none';
      });
    });
  }

  var filterBtn = document.getElementById('filter-btn');
  if (filterBtn) {
    var filterActive = false;
    filterBtn.addEventListener('click', function() {
      filterActive = !filterActive;
      if (filterActive) {
        filterBtn.classList.add('bg-primary/10', 'text-primary');
        filterBtn.classList.remove('text-text-secondary');
      } else {
        filterBtn.classList.remove('bg-primary/10', 'text-primary');
        filterBtn.classList.add('text-text-secondary');
      }
      
      var rows = document.querySelectorAll('#transactions-list-tbody tr');
      rows.forEach(function(row) {
        var isFlagged = row.textContent.includes('Flagged');
        if (filterActive && !isFlagged) {
          row.style.display = 'none';
          row.dataset.filtered = 'true';
        } else {
          row.dataset.filtered = 'false';
          row.style.display = '';
        }
      });
      
      if (searchInput && searchInput.value) {
          searchInput.dispatchEvent(new Event('input'));
      }
    });
  }
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

  var canvasEl = document.getElementById('txTimeChart');
  window.currentChart = new Chart(canvasEl, {
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

  var exportBtn = document.getElementById('export-data-btn');
  if (exportBtn) {
    exportBtn.addEventListener('click', function() {
      if (!globalState.transactions || !globalState.transactions.length) return;
      var keys = Object.keys(globalState.transactions[0]);
      var csv = keys.join(',') + '\n';
      globalState.transactions.forEach(function(t) {
        csv += keys.map(function(k) { return '"' + (t[k] || '') + '"'; }).join(',') + '\n';
      });
      var blob = new Blob([csv], { type: 'text/csv' });
      var url = window.URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.setAttribute('href', url);
      a.setAttribute('download', 'baseline_transactions.csv');
      a.click();
    });
  }
}

async function initConfig() {
  var inputs = {
    'LARGE_TXN_STDDEV_K': document.getElementById('input-sigma'),
    'LARGE_TXN_ABS_FLOOR': document.getElementById('input-floor-amount')
  };

  var saveBtn = document.getElementById('btn-save-config');

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
  } catch (err) {
    console.error("Failed to load config", err);
  }

  // Event Listeners
  if (saveBtn) {
    saveBtn.addEventListener('click', async function() {
      var prev = saveBtn.innerHTML;
      saveBtn.innerHTML = '<span class="material-symbols-rounded text-[18px] animate-spin">refresh</span> Saving...';
      
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
      } catch (err) {
        console.error("Failed to save configuration", err);
      } finally {
        setTimeout(() => { saveBtn.innerHTML = prev; }, 500);
      }
    });
  }
}

function initAudit() {
  var nameEl1 = document.getElementById('audit-customer-name');
  var nameEl2 = document.getElementById('audit-entity-name');
  
  if (globalState.selectedCustomerId) {
    var c = globalState.customers.find(function(c) { return c.customer_id == globalState.selectedCustomerId; });
    if (c) {
      if (nameEl1) nameEl1.textContent = c.full_name;
      if (nameEl2) nameEl2.textContent = c.full_name;
    }
  }

  var avgEl = document.getElementById('audit-stat-avg');
  if (avgEl && globalState.report) {
    avgEl.textContent = '\u20B9' + parseFloat(globalState.report.baseline_summary.avg_amount).toLocaleString('en-IN', {minimumFractionDigits:2});
  }

  var downloadPdfBtn = document.getElementById('downloadPdfBtn');
  if (downloadPdfBtn) {
    downloadPdfBtn.addEventListener('click', function() { window.print(); });
  }
  
  var printBtn = document.getElementById('print-btn');
  if (printBtn) {
    printBtn.addEventListener('click', function() { window.print(); });
  }

  var dateEl = document.getElementById('audit-date');
  if (dateEl) {
    var today = new Date();
    var options = { year: 'numeric', month: 'long', day: 'numeric' };
    dateEl.textContent = today.toLocaleDateString('en-US', options);
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
