/**
 * Smart Attendance System - Interactive Analytics Dashboard
 */

class AttendanceAnalyticsDashboard {
    constructor() {
        this.charts = {};
        this.filterForm = document.getElementById('analytics-filter-form');
        this.init();
    }

    init() {
        if (this.filterForm) {
            this.filterForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.loadAllData();
            });

            // Auto-submit on change
            const inputs = this.filterForm.querySelectorAll('select, input[type="date"]');
            inputs.forEach(input => {
                input.addEventListener('change', () => this.loadAllData());
            });
        }

        this.loadAllData();
    }

    getFilterParams() {
        if (!this.filterForm) return '';
        const formData = new FormData(this.filterForm);
        const params = new URLSearchParams();
        for (const [key, value] of formData.entries()) {
            if (value) params.append(key, value);
        }
        return params.toString();
    }

    async loadAllData() {
        const query = this.getFilterParams();
        try {
            await Promise.all([
                this.loadSummary(query),
                this.loadTrendChart(query),
                this.loadClasswiseChart(query),
                this.loadSubjectwiseChart(query),
                this.loadHeatmap(query),
                this.loadTopAbsentChart(query),
                this.loadDistributionChart(query)
            ]);
        } catch (err) {
            console.error("Analytics load error:", err);
            showToast("Failed to load some analytics data. Check console.", "error");
        }
    }

    async loadSummary(query) {
        const res = await fetch(`/analytics/api/summary?${query}`);
        if (!res.ok) return;
        const data = await res.json();

        this.setElText('kpi-total-students', data.total_students);
        this.setElText('kpi-total-teachers', data.total_teachers);
        this.setElText('kpi-active-classes', data.active_classes);
        this.setElText('kpi-today-present', `${data.today_present_pct}%`);
        this.setElText('kpi-avg-attendance', `${data.avg_attendance_pct}%`);
        this.setElText('kpi-below-threshold', data.students_below_threshold);
        this.setElText('kpi-sessions-today', data.sessions_today);
        this.setElText('kpi-face-coverage', `${data.face_coverage_pct}%`);
    }

    async loadTrendChart(query) {
        const res = await fetch(`/analytics/api/trend?${query}`);
        if (!res.ok) return;
        const data = await res.json();

        const ctx = document.getElementById('trend-chart');
        if (!ctx) return;

        if (this.charts.trend) this.charts.trend.destroy();

        this.charts.trend = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Attendance Rate (%)',
                    data: data.percentages,
                    borderColor: '#3B82F6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true,
                    tension: 0.35,
                    borderWidth: 3,
                    pointBackgroundColor: '#3B82F6',
                    pointRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => ` Attendance: ${ctx.raw}%`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: { callback: (v) => `${v}%` }
                    }
                }
            }
        });
    }

    async loadClasswiseChart(query) {
        const res = await fetch(`/analytics/api/classwise?${query}`);
        if (!res.ok) return;
        const data = await res.json();

        const ctx = document.getElementById('classwise-chart');
        if (!ctx) return;

        if (this.charts.classwise) this.charts.classwise.destroy();

        this.charts.classwise = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Average Attendance (%)',
                    data: data.percentages,
                    backgroundColor: '#10B981',
                    borderRadius: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, max: 100, ticks: { callback: (v) => `${v}%` } }
                }
            }
        });
    }

    async loadSubjectwiseChart(query) {
        const res = await fetch(`/analytics/api/subjectwise?${query}`);
        if (!res.ok) return;
        const data = await res.json();

        const ctx = document.getElementById('subjectwise-chart');
        if (!ctx) return;

        if (this.charts.subjectwise) this.charts.subjectwise.destroy();

        this.charts.subjectwise = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Subject Attendance (%)',
                    data: data.percentages,
                    backgroundColor: '#6366F1',
                    borderRadius: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, max: 100, ticks: { callback: (v) => `${v}%` } }
                }
            }
        });
    }

    async loadHeatmap(query) {
        const res = await fetch(`/analytics/api/heatmap?${query}`);
        if (!res.ok) return;
        const data = await res.json();

        const container = document.getElementById('heatmap-container');
        if (!container) return;

        let html = `
            <div class="overflow-x-auto">
                <table class="w-full text-xs text-center border-collapse">
                    <thead>
                        <tr>
                            <th class="p-2 border border-slate-200 dark:border-slate-800 text-left font-semibold text-slate-500">Day / Period</th>
                            ${data.periods.map(p => `<th class="p-2 border border-slate-200 dark:border-slate-800 font-semibold text-slate-600 dark:text-slate-300">${p}</th>`).join('')}
                        </tr>
                    </thead>
                    <tbody>
        `;

        data.weekdays.forEach((day, rIdx) => {
            html += `<tr><td class="p-2 border border-slate-200 dark:border-slate-800 font-bold text-left text-slate-700 dark:text-slate-300">${day}</td>`;
            data.data[rIdx].forEach(val => {
                const bg = this.getHeatmapColor(val);
                html += `
                    <td class="p-2 border border-slate-200 dark:border-slate-800 ${bg} font-semibold transition hover:scale-105" title="${val}% attendance">
                        ${val > 0 ? `${val}%` : '-'}
                    </td>
                `;
            });
            html += `</tr>`;
        });

        html += `</tbody></table></div>`;
        container.innerHTML = html;
    }

    getHeatmapColor(val) {
        if (val === 0) return 'bg-slate-50 dark:bg-slate-800/40 text-slate-400';
        if (val >= 90) return 'bg-emerald-500/20 text-emerald-800 dark:text-emerald-200';
        if (val >= 80) return 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300';
        if (val >= 75) return 'bg-amber-500/20 text-amber-800 dark:text-amber-200';
        if (val >= 60) return 'bg-orange-500/20 text-orange-800 dark:text-orange-200';
        return 'bg-rose-500/25 text-rose-800 dark:text-rose-200';
    }

    async loadTopAbsentChart(query) {
        const res = await fetch(`/analytics/api/top-absent?${query}`);
        if (!res.ok) return;
        const data = await res.json();

        const ctx = document.getElementById('top-absent-chart');
        if (!ctx) return;

        if (this.charts.topAbsent) this.charts.topAbsent.destroy();

        this.charts.topAbsent = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Absences Count',
                    data: data.counts,
                    backgroundColor: '#EF4444',
                    borderRadius: 6
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { beginAtZero: true }
                }
            }
        });
    }

    async loadDistributionChart(query) {
        const res = await fetch(`/analytics/api/distribution?${query}`);
        if (!res.ok) return;
        const data = await res.json();

        const ctx = document.getElementById('distribution-chart');
        if (!ctx) return;

        if (this.charts.distribution) this.charts.distribution.destroy();

        this.charts.distribution = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.labels,
                datasets: [{
                    data: data.counts,
                    backgroundColor: [
                        '#10B981', // 90-100%
                        '#3B82F6', // 80-89%
                        '#F59E0B', // 75-79%
                        '#F97316', // 60-74%
                        '#EF4444'  // Below 60%
                    ],
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { boxWidth: 12, font: { size: 11 } }
                    }
                }
            }
        });
    }

    setElText(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text !== undefined && text !== null ? text : '-';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('analytics-dashboard-page')) {
        window.analyticsApp = new AttendanceAnalyticsDashboard();
    }
});
