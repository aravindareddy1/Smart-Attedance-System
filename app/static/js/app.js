/**
 * Smart Attendance System - Core Application JS
 * Provides Universal showToast & App.toast with Deduplication
 */
(function () {
    const recentToasts = new Map();

    function showToast(arg1, arg2, duration = 3500) {
        let type = 'info';
        let message = '';

        // Flexible argument handling: (type, message) or (message, type)
        const validTypes = ['success', 'error', 'warning', 'info', 'danger'];
        if (validTypes.includes(String(arg1).toLowerCase())) {
            type = String(arg1).toLowerCase() === 'danger' ? 'error' : String(arg1).toLowerCase();
            message = String(arg2 || '');
        } else if (validTypes.includes(String(arg2).toLowerCase())) {
            message = String(arg1 || '');
            type = String(arg2).toLowerCase() === 'danger' ? 'error' : String(arg2).toLowerCase();
        } else {
            message = String(arg1 || '');
            type = 'info';
        }

        if (!message) return;

        // Deduplicate identical toasts within 2.5 seconds
        const now = Date.now();
        const key = `${type}:${message}`;
        if (recentToasts.has(key) && now - recentToasts.get(key) < 2500) {
            return;
        }
        recentToasts.set(key, now);

        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'fixed bottom-5 right-5 z-[9999] flex flex-col space-y-2 max-w-sm pointer-events-none';
            document.body.appendChild(container);
        }

        const bgColors = {
            success: 'bg-emerald-600 text-white',
            error: 'bg-rose-600 text-white',
            warning: 'bg-amber-500 text-white',
            info: 'bg-blue-600 text-white'
        };

        const toast = document.createElement('div');
        toast.className = `${bgColors[type] || bgColors.info} pointer-events-auto px-4 py-3 rounded-xl shadow-xl flex items-center justify-between text-xs font-semibold transition-all duration-300 transform translate-y-3 opacity-0`;
        toast.innerHTML = `
            <span class="flex-1 mr-2">${message}</span>
            <button class="text-white/80 hover:text-white font-bold text-base leading-none">&times;</button>
        `;

        toast.querySelector('button').addEventListener('click', () => {
            toast.remove();
        });

        container.appendChild(toast);

        requestAnimationFrame(() => {
            toast.classList.remove('translate-y-3', 'opacity-0');
        });

        setTimeout(() => {
            toast.classList.add('opacity-0', 'translate-y-3');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    // Attach to window and App namespace
    window.showToast = showToast;
    window.App = window.App || {};
    window.App.toast = showToast;
})();
