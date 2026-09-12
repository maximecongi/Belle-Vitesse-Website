/**
 * ios-bridge.js — Passerelle de communication entre l'Admin Belle Vitesse et l'application iPadOS Native (Swift / WKWebView).
 */

(function () {
    'use strict';

    const hasWebKitBridge = !!(
        window.webkit &&
        window.webkit.messageHandlers &&
        window.webkit.messageHandlers.bvBridge
    );

    const iosBridge = {
        isNativeApp: hasWebKitBridge,

        /**
         * Envoie un message sécurisé au conteneur natif Swift.
         * @param {string} action - L'action à déclencher (ex: 'haptic', 'sessionState', 'openExternal')
         * @param {object} payload - Données associées
         */
        postMessage: function (action, payload) {
            if (!this.isNativeApp) return;
            try {
                window.webkit.messageHandlers.bvBridge.postMessage({
                    action: action,
                    payload: payload || {}
                });
            } catch (err) {
                console.warn('[BV iPad Bridge] Échec d’envoi de message :', err);
            }
        },

        /**
         * Déclenche un retour haptique sur l'iPad (si compatible).
         * @param {'light'|'medium'|'heavy'|'success'|'warning'|'error'|'selection'} type
         */
        triggerHaptic: function (type) {
            this.postMessage('haptic', { type: type || 'selection' });
        },

        /**
         * Notifie l'application native d'un état d'authentification ou d'une page chargée.
         */
        notifyReady: function () {
            this.postMessage('pageReady', {
                path: window.location.pathname,
                title: document.title
            });
        }
    };

    window.bvIpadBridge = iosBridge;

    // Déclencheurs haptiques automatiques sur les interactions réussies
    document.addEventListener('DOMContentLoaded', function () {
        if (iosBridge.isNativeApp) {
            document.documentElement.classList.add('is-bv-ipad-native');
            iosBridge.notifyReady();

            // Retours haptiques sur les messages Flash (succès / alerte)
            const successFlash = document.querySelector('.flash-success');
            if (successFlash) {
                iosBridge.triggerHaptic('success');
            }
            const errorFlash = document.querySelector('.flash-error, .flash-danger');
            if (errorFlash) {
                iosBridge.triggerHaptic('error');
            }
        }
    });
})();
