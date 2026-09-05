/**
 * charts.js — Initialisation des graphiques Chart.js du tableau de bord.
 */

function initDashboardCharts() {
    const monthlyCanvas = document.getElementById('monthlyChart');
    if (monthlyCanvas && typeof Chart !== 'undefined' && !monthlyCanvas.dataset.initialized) {
        monthlyCanvas.dataset.initialized = 'true';

        fetch('/admin/api/stats')
            .then(response => response.json())
            .then(data => {
                new Chart(monthlyCanvas, {
                    type: 'bar',
                    data: {
                        labels: data.monthly_activity.labels,
                        datasets: [{
                            label: 'Nombre de checkouts',
                            data: data.monthly_activity.data,
                            backgroundColor: '#FFC845',
                            borderRadius: 4
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: { legend: { display: false } },
                        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
                    }
                });

                const statusCanvas = document.getElementById('statusChart');
                if (statusCanvas) {
                    new Chart(statusCanvas, {
                        type: 'doughnut',
                        data: {
                            labels: data.status_distribution.labels,
                            datasets: [{
                                data: data.status_distribution.data,
                                backgroundColor: ['#28a745', '#f59e0b', '#dc3545', '#6c757d']
                            }]
                        },
                        options: {
                            responsive: true,
                            plugins: { legend: { position: 'bottom' } }
                        }
                    });
                }
            })
            .catch(error => console.error('Error fetching stats:', error));
    }
}

window.initDashboardCharts = initDashboardCharts;
