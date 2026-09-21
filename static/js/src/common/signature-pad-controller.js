/**
 * signature-pad-controller.js — Contrôleur mutualisé pour SignaturePad (Belle Vitesse)
 *
 * Automatise :
 * - Le scaling Retina / HiDPI (devicePixelRatio)
 * - La gestion dynamique du redimensionnement de fenêtre
 * - L'effacement via bouton de reset
 * - L'export PNG base64 et la vérification de conformité (non-vide)
 */
class BelleVitesseSignaturePad {
    constructor(canvasId = 'signature-canvas', options = {}) {
        this.canvas = typeof canvasId === 'string' ? document.getElementById(canvasId) : canvasId;
        if (!this.canvas) return;

        this.wrapper = this.canvas.parentElement;
        this.clearBtn = options.clearBtnId
            ? document.getElementById(options.clearBtnId)
            : (document.getElementById('btn-clear') || document.getElementById('clear-signature'));

        const padOptions = Object.assign({
            backgroundColor: 'rgb(250, 250, 250)',
            penColor: 'rgb(21, 21, 21)'
        }, options.padOptions || {});

        if (typeof SignaturePad !== 'undefined') {
            this.pad = new SignaturePad(this.canvas, padOptions);
            this._initEvents();
            this.resize();
        } else {
            console.warn('[BelleVitesseSignaturePad] SignaturePad library not loaded.');
        }
    }

    resize() {
        if (!this.canvas || !this.wrapper) return;
        const ratio = Math.max(window.devicePixelRatio || 1, 1);
        this.canvas.width = this.wrapper.offsetWidth * ratio;
        this.canvas.height = this.wrapper.offsetHeight * ratio;
        const ctx = this.canvas.getContext('2d');
        if (ctx) ctx.scale(ratio, ratio);
        if (this.pad) this.pad.clear();
    }

    clear() {
        if (this.pad) this.pad.clear();
    }

    isEmpty() {
        return !this.pad || this.pad.isEmpty();
    }

    toDataURL(type = 'image/png') {
        return this.pad ? this.pad.toDataURL(type) : '';
    }

    _initEvents() {
        window.addEventListener('resize', () => this.resize());
        if (this.clearBtn) {
            this.clearBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.clear();
            });
        }
    }
}

// Export global pour scripts modulaires ou inline
window.BelleVitesseSignaturePad = BelleVitesseSignaturePad;
