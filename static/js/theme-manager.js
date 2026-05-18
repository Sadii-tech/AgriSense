// static/js/theme-manager.js
// Centralized theme management for the entire application

class ThemeManager {
    constructor() {
        this.THEME_KEY = 'agrisense_theme';
        this.body = document.body;
        this.isUpdating = false;
        this.isFirstLoad = true;
        this.init();
    }

    init() {
        this.loadTheme();
        
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            // Do nothing - user preference takes priority
        });
        
        window.addEventListener('storage', (e) => {
            if (e.key === this.THEME_KEY && e.newValue) {
                this.applyTheme(e.newValue, false);
            }
        });
        
        window.addEventListener('themeChanged', (e) => {
            if (e.detail && e.detail.theme) {
                this.applyTheme(e.detail.theme, true);
            }
        });
        
        this.setupThemeToggles();
    }
    
    async loadTheme() {
        let theme = null;
        
        // ALWAYS fetch from database first (source of truth)
        try {
            const response = await fetch('/api/get-theme/');
            const data = await response.json();
            if (data.success && data.theme) {
                theme = data.theme;
                // Sync localStorage with database
                localStorage.setItem(this.THEME_KEY, theme);
                console.log('Theme loaded from database:', theme);
            }
        } catch(e) {
            console.log('Could not fetch theme from server, checking localStorage');
        }
        
        // Fallback to localStorage if database fetch failed
        if (!theme) {
            theme = localStorage.getItem(this.THEME_KEY);
        }
        
        // Final fallback to light mode
        if (!theme) {
            theme = 'light';
        }
        
        // Apply theme WITHOUT saving to server (first load)
        this.applyTheme(theme, false);
        this.isFirstLoad = false;
    }

    applyTheme(theme, saveToServer = true) {
        if (this.isUpdating) return;
        this.isUpdating = true;
        
        if (theme === 'dark') {
            this.body.classList.add('dark');
        } else {
            this.body.classList.remove('dark');
        }
        
        this.updateToggleUI(theme);
        localStorage.setItem(this.THEME_KEY, theme);
        
        // Only save to server if it's a manual change (user toggle) and not first load
        if (saveToServer && !this.isFirstLoad) {
            this.saveToServer(theme);
        }
        
        window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme } }));
        
        this.isUpdating = false;
    }

    async saveToServer(theme) {
        try {
            const response = await fetch('/api/save-theme/', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json', 
                    'X-CSRFToken': this.getCsrfToken() 
                },
                body: JSON.stringify({ theme: theme })
            });
            const data = await response.json();
            if (data.success) {
                console.log('Theme saved to server:', theme);
                // Also update localStorage to stay in sync
                localStorage.setItem(this.THEME_KEY, theme);
            } else {
                console.log('Failed to save theme to server');
            }
        } catch(e) { 
            console.log('Error saving theme:', e); 
        }
    }

    toggleTheme() {
        const newTheme = this.body.classList.contains('dark') ? 'light' : 'dark';
        this.applyTheme(newTheme, true);
        return newTheme;
    }

    getCurrentTheme() {
        return this.body.classList.contains('dark') ? 'dark' : 'light';
    }

    updateToggleUI(theme) {
        const toggles = document.querySelectorAll('#themeToggleCheckbox, #themeToggleCheckboxSettings');
        toggles.forEach(toggle => {
            if (toggle && toggle.checked !== (theme === 'dark')) {
                toggle.checked = (theme === 'dark');
            }
        });
        
        const themeButtons = document.querySelectorAll('#theme-toggle-btn, #themeToggleBtn');
        themeButtons.forEach(btn => {
            if (btn) {
                const iconSpan = btn.querySelector('.material-symbols-outlined');
                if (iconSpan) {
                    iconSpan.textContent = (theme === 'dark') ? 'light_mode' : 'dark_mode';
                }
                if (btn.querySelector('span:not(.material-symbols-outlined)')) {
                    const textSpan = btn.querySelector('span:not(.material-symbols-outlined)');
                    if (textSpan) {
                        textSpan.textContent = (theme === 'dark') ? 'Light' : 'Dark';
                    }
                }
            }
        });
    }

    setupThemeToggles() {
        const checkboxes = document.querySelectorAll('#themeToggleCheckbox, #themeToggleCheckboxSettings');
        
        checkboxes.forEach(checkbox => {
            const newCheckbox = checkbox.cloneNode(true);
            if (checkbox.parentNode) {
                checkbox.parentNode.replaceChild(newCheckbox, checkbox);
            }
            
            newCheckbox.addEventListener('change', (e) => {
                e.stopPropagation();
                if (this.isUpdating) return;
                
                const newTheme = newCheckbox.checked ? 'dark' : 'light';
                const currentTheme = this.getCurrentTheme();
                
                if (newTheme !== currentTheme) {
                    this.applyTheme(newTheme, true);
                    this.showToast(`${newTheme === 'dark' ? 'Dark' : 'Light'} mode activated`);
                }
            });
        });
        
        const buttons = document.querySelectorAll('#theme-toggle-btn, #themeToggleBtn');
        buttons.forEach(button => {
            const newButton = button.cloneNode(true);
            if (button.parentNode) {
                button.parentNode.replaceChild(newButton, button);
            }
            
            newButton.addEventListener('click', (e) => {
                e.preventDefault();
                const newTheme = this.toggleTheme();
                this.showToast(`${newTheme === 'dark' ? 'Dark' : 'Light'} mode activated`);
            });
        });
    }

    getCsrfToken() {
        return document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1];
    }

    showToast(message, type = 'success') {
        let toast = document.getElementById('theme-toast');
        
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'theme-toast';
            toast.style.cssText = `
                position: fixed;
                bottom: 2rem;
                right: 2rem;
                z-index: 10000;
                padding: 0.75rem 1.25rem;
                border-radius: 0.75rem;
                display: none;
                background: white;
                border: 1px solid #d4e8ce;
                box-shadow: 0 8px 20px rgba(0,0,0,0.08);
                font-family: 'Inter', sans-serif;
                font-size: 0.875rem;
                font-weight: 500;
                align-items: center;
                gap: 0.5rem;
            `;
            document.body.appendChild(toast);
            
            const iconSpan = document.createElement('span');
            iconSpan.className = 'material-symbols-outlined';
            iconSpan.style.fontSize = '18px';
            const textSpan = document.createElement('span');
            
            toast.appendChild(iconSpan);
            toast.appendChild(textSpan);
        }
        
        const iconSpan = toast.querySelector('.material-symbols-outlined');
        const textSpan = toast.querySelector('span:not(.material-symbols-outlined)');
        
        if (!iconSpan || !textSpan) return;
        
        textSpan.textContent = message;
        
        if (type === 'error') {
            iconSpan.textContent = 'error';
            iconSpan.style.color = '#e53e3e';
            toast.style.borderColor = '#fecaca';
        } else {
            iconSpan.textContent = 'check_circle';
            iconSpan.style.color = '#10b981';
            toast.style.borderColor = '#bbf7d0';
        }
        
        if (this.body.classList.contains('dark')) {
            toast.style.background = '#121a12';
            toast.style.borderColor = '#2a3a2a';
            textSpan.style.color = '#e5ede3';
        } else {
            toast.style.background = 'white';
            toast.style.borderColor = '#d4e8ce';
            textSpan.style.color = '#1a2c1e';
        }
        
        toast.style.display = 'flex';
        setTimeout(() => {
            toast.style.display = 'none';
        }, 2000);
    }
}

// Initialize theme manager when DOM is loaded
if (typeof window !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
        window.themeManager = new ThemeManager();
    });
}