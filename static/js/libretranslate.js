// static/js/libretranslate.js
// LibreTranslate Integration - Completely Free

class LibreTranslateManager {
    constructor() {
        this.currentLang = 'en';
        this.isTranslating = false;
        this.cache = new Map();
        this.init();
    }

    async init() {
        await this.loadPreference();
        this.setupButtons();
        this.updateUI();
        
        // Auto-translate if Urdu was previously selected
        if (this.currentLang === 'ur') {
            setTimeout(() => this.translatePage(), 500);
        }
    }

    async loadPreference() {
        try {
            const response = await fetch('/api/get-language-preference/');
            const data = await response.json();
            if (data.success) {
                this.currentLang = data.language;
            }
        } catch (error) {
            // Fallback to localStorage
            const saved = localStorage.getItem('libretranslate_lang');
            if (saved) this.currentLang = saved;
        }
    }

    async savePreference(lang) {
        try {
            await fetch('/api/set-language-preference/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({ language: lang })
            });
        } catch (error) {
            localStorage.setItem('libretranslate_lang', lang);
        }
        this.currentLang = lang;
    }

    async translatePage() {
        if (this.isTranslating) return;
        this.isTranslating = true;

        // Collect all text elements
        const elements = this.getTextElements();
        
        const textsToTranslate = [];
        const elementMap = [];

        elements.forEach(el => {
            const text = el.innerText.trim();
            if (text && text.length > 0 && text.length < 500) {
                // Check cache first
                if (this.cache.has(text)) {
                    el.innerText = this.cache.get(text);
                } else {
                    textsToTranslate.push(text);
                    elementMap.push(el);
                }
            }
        });

        if (textsToTranslate.length === 0) {
            this.isTranslating = false;
            return;
        }

        this.showLoading();

        try {
            const response = await fetch('/api/translate-page/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({
                    texts: textsToTranslate,
                    target_lang: 'ur'
                })
            });

            const data = await response.json();

            if (data.success) {
                let count = 0;
                data.translated_texts.forEach((translated, index) => {
                    if (elementMap[index] && translated && translated !== textsToTranslate[index]) {
                        // Store original text
                        if (!elementMap[index].hasAttribute('data-original')) {
                            elementMap[index].setAttribute('data-original', textsToTranslate[index]);
                        }
                        // Cache translation
                        this.cache.set(textsToTranslate[index], translated);
                        elementMap[index].innerText = translated;
                        count++;
                    }
                });
                this.showToast(`Translated ${count} items to Urdu! ✓`);
                await this.savePreference('ur');
                this.updateUI();
            } else {
                this.showToast('Translation failed. Please try again.', true);
            }
        } catch (error) {
            console.error('Translation error:', error);
            this.showToast('Network error. Please try again.', true);
        }

        this.hideLoading();
        this.isTranslating = false;
    }

    getTextElements() {
        // Select all text-containing elements
        const selectors = [
            'h1', 'h2', 'h3', 'h4', 'h5', 'p',
            '.sidebar-link', '.glass-card p', '.stat-badge',
            'button:not(.language-btn)', 'label', '.text-sm', '.text-lg'
        ];
        
        let elements = [];
        selectors.forEach(selector => {
            document.querySelectorAll(selector).forEach(el => {
                // Skip elements with icons, navigation, modals
                if (el.closest('.language-switch')) return;
                if (el.closest('#toast')) return;
                if (el.querySelector('.material-symbols-outlined')) return;
                if (el.closest('.team-card')) return;
                if (el.closest('.modal')) return;
                if (el.id === 'currentLanguage') return;
                elements.push(el);
            });
        });
        
        // Remove duplicates
        return [...new Set(elements)];
    }

    revertToEnglish() {
        // Reload page to reset translations
        location.reload();
    }

    setupButtons() {
        // Urdu translation button
        document.querySelectorAll('[data-lang="ur"]').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.preventDefault();
                await this.translatePage();
            });
        });

        // English button
        document.querySelectorAll('[data-lang="en"]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                this.savePreference('en');
                this.revertToEnglish();
            });
        });
    }

    updateUI() {
        // Update desktop dropdown
        document.querySelectorAll('.language-option').forEach(opt => {
            opt.classList.remove('active');
            if (opt.dataset.lang === this.currentLang) {
                opt.classList.add('active');
            }
        });
        
        // Update mobile options
        document.querySelectorAll('.mobile-lang-option').forEach(opt => {
            opt.classList.remove('active');
            if (opt.dataset.lang === this.currentLang) {
                opt.classList.add('active');
                opt.style.background = 'rgba(255,255,255,0.2)';
            } else {
                opt.style.background = 'rgba(255,255,255,0.1)';
            }
        });
        
        // Update language button text
        const currentLangSpan = document.getElementById('currentLanguage');
        if (currentLangSpan) {
            currentLangSpan.textContent = this.currentLang === 'en' ? 'English' : 'اردو';
        }
    }

    showLoading() {
        let loader = document.getElementById('libretranslate-loader');
        if (!loader) {
            loader = document.createElement('div');
            loader.id = 'libretranslate-loader';
            loader.innerHTML = `
                <div style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: #10b981; color: white; padding: 12px 24px; border-radius: 12px; z-index: 10000; display: flex; align-items: center; gap: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.2);">
                    <div class="libre-spinner"></div>
                    <span>Translating to Urdu with LibreTranslate...</span>
                </div>
                <style>
                    .libre-spinner {
                        width: 18px;
                        height: 18px;
                        border: 2px solid rgba(255,255,255,0.3);
                        border-top-color: white;
                        border-radius: 50%;
                        animation: libre-spin 0.6s linear infinite;
                    }
                    @keyframes libre-spin {
                        to { transform: rotate(360deg); }
                    }
                </style>
            `;
            document.body.appendChild(loader);
        }
        loader.style.display = 'block';
    }

    hideLoading() {
        const loader = document.getElementById('libretranslate-loader');
        if (loader) loader.style.display = 'none';
    }

    showToast(message, isError = false) {
        let toast = document.getElementById('libretranslate-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'libretranslate-toast';
            toast.style.cssText = `
                position: fixed;
                bottom: 80px;
                right: 20px;
                background: white;
                border: 1px solid #d4e8ce;
                border-radius: 12px;
                padding: 12px 20px;
                z-index: 10000;
                font-family: 'Inter', sans-serif;
                font-size: 14px;
                display: none;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            `;
            document.body.appendChild(toast);
        }
        
        toast.innerHTML = `
            <div style="display: flex; align-items: center; gap: 10px;">
                <span class="material-symbols-outlined" style="color: ${isError ? '#e53e3e' : '#10b981'}">
                    ${isError ? 'error' : 'check_circle'}
                </span>
                <span>${message}</span>
            </div>
        `;
        
        toast.style.display = 'block';
        setTimeout(() => toast.style.display = 'none', 3000);
    }

    getCsrfToken() {
        const cookieValue = document.cookie.split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
        return cookieValue;
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    window.libretranslate = new LibreTranslateManager();
});