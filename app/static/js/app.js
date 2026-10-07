/**
 * Smart Attendance System - Global Application JavaScript
 */

// ==========================================
// 1. THEME SWITCHER (Dark / Light Mode)
// ==========================================
function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

    if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
        document.documentElement.classList.add('dark');
    } else {
        document.documentElement.classList.remove('dark');
    }
}

function toggleTheme() {
    if (document.documentElement.classList.contains('dark')) {
        document.documentElement.classList.remove('dark');
        localStorage.setItem('theme', 'light');
    } else {
        document.documentElement.classList.add('dark');
        localStorage.setItem('theme', 'dark');
    }
}

// ==========================================
// 2. TOAST NOTIFICATION COMPONENT
// ==========================================
function showToast(message, type = 'info', duration = 4500) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'fixed bottom-5 right-5 z-50 flex flex-col space-y-3 max-w-sm w-full pointer-events-none';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `pointer-events-auto transform transition-all duration-300 ease-out translate-y-4 opacity-0 p-4 rounded-xl shadow-xl flex items-start space-x-3 text-sm font-medium border ${getToastStyle(type)}`;

    const icon = getToastIcon(type);
    toast.innerHTML = `
        <div class="flex-shrink-0 mt-0.5">${icon}</div>
        <div class="flex-1 text-slate-800 dark:text-slate-100">${escapeHtml(message)}</div>
        <button type="button" class="flex-shrink-0 ml-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200" onclick="this.parentElement.remove()">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
        </button>
    `;

    container.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => {
        toast.classList.remove('translate-y-4', 'opacity-0');
        toast.classList.add('translate-y-0', 'opacity-100');
    });

    // Auto dismiss
    if (duration > 0) {
        setTimeout(() => {
            toast.classList.add('opacity-0', 'translate-y-2');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }
}

function getToastStyle(type) {
    switch (type) {
        case 'success':
            return 'bg-emerald-50 dark:bg-emerald-950/80 border-emerald-300 dark:border-emerald-800 text-emerald-900 dark:text-emerald-100';
        case 'danger':
        case 'error':
            return 'bg-rose-50 dark:bg-rose-950/80 border-rose-300 dark:border-rose-800 text-rose-900 dark:text-rose-100';
        case 'warning':
            return 'bg-amber-50 dark:bg-amber-950/80 border-amber-300 dark:border-amber-800 text-amber-900 dark:text-amber-100';
        default:
            return 'bg-indigo-50 dark:bg-slate-900 border-indigo-200 dark:border-slate-700 text-indigo-900 dark:text-slate-100';
    }
}

function getToastIcon(type) {
    switch (type) {
        case 'success':
            return `<svg class="w-5 h-5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>`;
        case 'danger':
        case 'error':
            return `<svg class="w-5 h-5 text-rose-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`;
        case 'warning':
            return `<svg class="w-5 h-5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>`;
        default:
            return `<svg class="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==========================================
// 3. CONFIRMATION DIALOG MODAL
// ==========================================
function confirmDialog(title, message, confirmBtnText = 'Confirm', onConfirm = null) {
    const modalId = 'confirm-action-modal';
    let modal = document.getElementById(modalId);
    if (modal) modal.remove();

    modal = document.createElement('div');
    modal.id = modalId;
    modal.className = 'fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm';
    modal.innerHTML = `
        <div class="bg-white dark:bg-slate-900 rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 dark:border-slate-800 transform transition-all scale-100">
            <div class="flex items-center space-x-3 mb-4">
                <div class="p-3 bg-rose-100 dark:bg-rose-950/60 text-rose-600 rounded-xl">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                </div>
                <div>
                    <h3 class="text-lg font-bold text-slate-900 dark:text-slate-100">${escapeHtml(title)}</h3>
                    <p class="text-xs text-slate-500">Please confirm your action</p>
                </div>
            </div>
            <p class="text-sm text-slate-600 dark:text-slate-300 mb-6 leading-relaxed">${escapeHtml(message)}</p>
            <div class="flex items-center justify-end space-x-3">
                <button type="button" class="px-4 py-2 text-sm font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition" onclick="document.getElementById('${modalId}').remove()">
                    Cancel
                </button>
                <button type="button" id="confirm-modal-submit-btn" class="px-5 py-2 text-sm font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-xl shadow-md transition">
                    ${escapeHtml(confirmBtnText)}
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    document.getElementById('confirm-modal-submit-btn').addEventListener('click', () => {
        modal.remove();
        if (typeof onConfirm === 'function') {
            onConfirm();
        }
    });
}

// ==========================================
// 4. MOBILE SIDEBAR TOGGLE
// ==========================================
function toggleSidebar() {
    const sidebar = document.getElementById('app-sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (!sidebar) return;

    if (sidebar.classList.contains('-translate-x-full')) {
        sidebar.classList.remove('-translate-x-full');
        if (overlay) overlay.classList.remove('hidden');
    } else {
        sidebar.classList.add('-translate-x-full');
        if (overlay) overlay.classList.add('hidden');
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    initTheme();

    // Attach theme toggle button
    const themeBtn = document.getElementById('theme-toggle-btn');
    if (themeBtn) {
        themeBtn.addEventListener('click', toggleTheme);
    }

    // Attach mobile sidebar button
    const sidebarBtn = document.getElementById('sidebar-toggle-btn');
    if (sidebarBtn) {
        sidebarBtn.addEventListener('click', toggleSidebar);
    }
    const overlay = document.getElementById('sidebar-overlay');
    if (overlay) {
        overlay.addEventListener('click', toggleSidebar);
    }
});
