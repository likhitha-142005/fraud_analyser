// dashboard.js — shared JS utilities

// Auto-refresh stats every 60 seconds on dashboard

if (document.querySelector('.stats-grid')) {

  setInterval(() => {

    fetch('/api/stats')

      .then(r => r.json())

      .then(data => {

        const els = document.querySelectorAll('.stat-value');

        if (els.length > 0) console.log('Stats refreshed:', data);

      }).catch(() => {});

  }, 60000);

}

// Highlight table row on click

document.querySelectorAll('.data-table tbody tr').forEach(row => {

  row.style.cursor = 'pointer';

  row.addEventListener('click', (e) => {

    if (e.target.tagName === 'A') return;

    const link = row.querySelector('a');

    if (link) window.location = link.href;

  });

});

// Auto-dismiss alerts after 4 seconds

document.querySelectorAll('.alert').forEach(alert => {

  setTimeout(() => {

    alert.style.transition = 'opacity 0.5s';

    alert.style.opacity = '0';

    setTimeout(() => alert.remove(), 500);

  }, 4000);

});

  