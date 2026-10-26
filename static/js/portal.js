/**
 * NovaFlix - Plex-Style Showcase & Multi-Platform Download Portal JS
 * Handles OS switcher, variant download matrix, sign-up modal, and demo launcher.
 */

class NovaFlixPortal {
    constructor() {
        this.selectedOS = 'windows';
        this.initEventListeners();
    }

    initEventListeners() {
        // OS Tab Buttons
        document.querySelectorAll('.os-tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.os-tab-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.switchOS(btn.dataset.os);
            });
        });

        // Sign Up Modal
        const btnSignUp = document.getElementById('btnPortalSignUp');
        if (btnSignUp) {
            btnSignUp.addEventListener('click', () => this.openSignUpModal());
        }

        const signupForm = document.getElementById('portalSignupForm');
        if (signupForm) {
            signupForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleSignUp();
            });
        }
    }

    switchOS(os) {
        this.selectedOS = os;
        document.querySelectorAll('.download-os-group').forEach(group => {
            group.style.display = group.dataset.os === os ? 'grid' : 'none';
        });
    }

    openSignUpModal() {
        const modal = document.getElementById('signupModal');
        if (modal) modal.classList.add('active');
    }

    closeSignUpModal() {
        const modal = document.getElementById('signupModal');
        if (modal) modal.classList.remove('active');
    }

    async handleSignUp() {
        const username = document.getElementById('signupUsername').value.trim();
        const password = document.getElementById('signupPassword').value.trim();
        const statusEl = document.getElementById('signupStatus');

        if (!username || !password) return;

        try {
            statusEl.innerText = 'Creating sovereign account...';
            statusEl.style.color = 'var(--text-secondary)';

            const res = await fetch('/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            const data = await res.json();

            if (res.ok) {
                statusEl.innerText = 'Account created successfully! Redirecting to Cinema app...';
                statusEl.style.color = 'var(--emerald-safe)';
                setTimeout(() => {
                    window.location.href = '/';
                }, 1500);
            } else {
                statusEl.innerText = data.detail || 'Registration failed';
                statusEl.style.color = 'var(--rose-danger)';
            }
        } catch (e) {
            statusEl.innerText = `Error: ${e}`;
            statusEl.style.color = 'var(--rose-danger)';
        }
    }

    triggerDownload(filename) {
        let downloadUrl = `/downloads/${filename}`;
        if (filename.startsWith('http://') || filename.startsWith('https://')) {
            downloadUrl = filename;
        } else if (filename.startsWith('/')) {
            downloadUrl = filename;
        }
        
        // Trigger browser download
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    copyCommand(text, btnId) {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text).then(() => {
                const btn = document.getElementById(btnId);
                if (btn) {
                    const orig = btn.innerText;
                    btn.innerText = 'Copied!';
                    setTimeout(() => { btn.innerText = orig; }, 2500);
                }
            });
        }
    }
}

window.portal = new NovaFlixPortal();
