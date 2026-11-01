/**
 * draft-store.js — Moteur universel de persistance locale (IndexedDB + fallback localStorage)
 * pour les formulaires de l'ERP Belle Vitesse (Inspections et Incidents).
 *
 * Supporte le stockage transactionnel des champs de formulaire ET des fichiers binaires (Blobs/Files)
 * sans limitation de quota arbitraire, garantissant une résilience maximale sur le terrain.
 */

(function () {
    'use strict';

    const DB_NAME = 'bv_drafts_db';
    const DB_VERSION = 1;
    const STORE_NAME = 'drafts';
    const DEFAULT_MAX_AGE_MS = 48 * 60 * 60 * 1000; // 48 heures
    const LOCAL_STORAGE_PREFIX = 'bv_draft_fb_';

    let dbInstance = null;
    let indexedDbSupported = typeof window !== 'undefined' && 'indexedDB' in window;

    /**
     * Ouvre ou initialise la base de données IndexedDB.
     * @returns {Promise<IDBDatabase>}
     */
    function getDatabase() {
        if (dbInstance) {
            return Promise.resolve(dbInstance);
        }

        if (!indexedDbSupported) {
            return Promise.reject(new Error('IndexedDB non supporté par cet environnement'));
        }

        return new Promise((resolve, reject) => {
            try {
                const request = indexedDB.open(DB_NAME, DB_VERSION);

                request.onupgradeneeded = function (event) {
                    const db = event.target.result;
                    if (!db.objectStoreNames.contains(STORE_NAME)) {
                        const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
                        store.createIndex('timestamp', 'timestamp', { unique: false });
                        store.createIndex('formType', 'formType', { unique: false });
                    }
                };

                request.onsuccess = function (event) {
                    dbInstance = event.target.result;
                    dbInstance.onversionchange = function () {
                        dbInstance.close();
                        dbInstance = null;
                    };
                    resolve(dbInstance);
                };

                request.onerror = function (event) {
                    console.warn('⚠️ Échec ouverture IndexedDB, bascule vers localStorage :', event.target.error);
                    resolve(null); // Bascule douce vers fallback
                };

                request.onblocked = function () {
                    console.warn('⚠️ Base IndexedDB bloquée par une autre instance');
                    resolve(null);
                };
            } catch (err) {
                console.warn('⚠️ Exception lors de l’accès à IndexedDB :', err);
                resolve(null);
            }
        });
    }

    /**
     * Fallback localStorage : sauvegarde des champs scalaires uniquement (pas de fichiers).
     */
    function saveToLocalStorageFallback(key, payload) {
        try {
            const safePayload = {
                id: payload.id,
                formType: payload.formType,
                pathname: payload.pathname,
                projectId: payload.projectId,
                vehicleId: payload.vehicleId,
                timestamp: payload.timestamp || Date.now(),
                fields: payload.fields || {},
                filesCount: Object.keys(payload.files || {}).reduce((acc, k) => acc + (payload.files[k] || []).length, 0),
                isFallback: true
            };
            localStorage.setItem(LOCAL_STORAGE_PREFIX + encodeURIComponent(key), JSON.stringify(safePayload));
            return true;
        } catch (e) {
            console.warn('⚠️ Impossible d’écrire dans localStorage :', e);
            return false;
        }
    }

    /**
     * Fallback localStorage : lecture.
     */
    function getFromLocalStorageFallback(key) {
        try {
            const raw = localStorage.getItem(LOCAL_STORAGE_PREFIX + encodeURIComponent(key));
            if (!raw) return null;
            const data = JSON.parse(raw);
            const age = Date.now() - (data.timestamp || 0);
            if (age > DEFAULT_MAX_AGE_MS) {
                localStorage.removeItem(LOCAL_STORAGE_PREFIX + encodeURIComponent(key));
                return null;
            }
            return data;
        } catch (e) {
            return null;
        }
    }

    /**
     * Fallback localStorage : suppression.
     */
    function removeFromLocalStorageFallback(key) {
        try {
            localStorage.removeItem(LOCAL_STORAGE_PREFIX + encodeURIComponent(key));
        } catch (e) {
            // Ignorer
        }
    }

    const BvDraftStore = {
        /**
         * Sauvegarde un brouillon (champs scalaires + fichiers binaires).
         * @param {string} key Identifiant unique du brouillon
         * @param {Object} data Données du brouillon { formType, pathname, projectId, vehicleId, fields, files, metadata }
         * @returns {Promise<boolean>}
         */
        saveDraft: async function (key, data) {
            if (!key) return false;

            const record = {
                id: key,
                formType: data.formType || 'generic',
                pathname: data.pathname || window.location.pathname,
                projectId: data.projectId || '',
                vehicleId: data.vehicleId || '',
                timestamp: Date.now(),
                fields: data.fields || {},
                files: data.files || {},
                metadata: data.metadata || {}
            };

            const db = await getDatabase();
            if (!db) {
                return saveToLocalStorageFallback(key, record);
            }

            return new Promise((resolve) => {
                try {
                    const tx = db.transaction(STORE_NAME, 'readwrite');
                    const store = tx.objectStore(STORE_NAME);
                    const req = store.put(record);

                    req.onsuccess = () => resolve(true);
                    req.onerror = (e) => {
                        console.warn('⚠️ Erreur écriture IndexedDB, tentative fallback :', e.target.error);
                        resolve(saveToLocalStorageFallback(key, record));
                    };
                } catch (txErr) {
                    console.warn('⚠️ Transaction IndexedDB échouée :', txErr);
                    resolve(saveToLocalStorageFallback(key, record));
                }
            });
        },

        /**
         * Récupère un brouillon existant s'il n'a pas expiré (TTL 48h).
         * @param {string} key
         * @returns {Promise<Object|null>}
         */
        loadDraft: async function (key) {
            if (!key) return null;

            const db = await getDatabase();
            if (!db) {
                return getFromLocalStorageFallback(key);
            }

            return new Promise((resolve) => {
                try {
                    const tx = db.transaction(STORE_NAME, 'readonly');
                    const store = tx.objectStore(STORE_NAME);
                    const req = store.get(key);

                    req.onsuccess = (e) => {
                        const result = e.target.result;
                        if (!result) {
                            resolve(getFromLocalStorageFallback(key));
                            return;
                        }

                        const age = Date.now() - (result.timestamp || 0);
                        if (age > DEFAULT_MAX_AGE_MS) {
                            BvDraftStore.deleteDraft(key);
                            resolve(null);
                            return;
                        }

                        resolve(result);
                    };

                    req.onerror = () => {
                        resolve(getFromLocalStorageFallback(key));
                    };
                } catch (err) {
                    resolve(getFromLocalStorageFallback(key));
                }
            });
        },

        /**
         * Supprime définitivement un brouillon par sa clé.
         * @param {string} key
         * @returns {Promise<boolean>}
         */
        deleteDraft: async function (key) {
            if (!key) return true;

            removeFromLocalStorageFallback(key);

            const db = await getDatabase();
            if (!db) return true;

            return new Promise((resolve) => {
                try {
                    const tx = db.transaction(STORE_NAME, 'readwrite');
                    const store = tx.objectStore(STORE_NAME);
                    const req = store.delete(key);

                    req.onsuccess = () => resolve(true);
                    req.onerror = () => resolve(false);
                } catch (err) {
                    resolve(false);
                }
            });
        },

        /**
         * Nettoie tous les brouillons périmés (TTL > 48h).
         */
        cleanStaleDrafts: async function () {
            const db = await getDatabase();
            if (!db) return;

            try {
                const tx = db.transaction(STORE_NAME, 'readwrite');
                const store = tx.objectStore(STORE_NAME);
                const req = store.openCursor();

                const now = Date.now();
                req.onsuccess = function (e) {
                    const cursor = e.target.result;
                    if (cursor) {
                        const val = cursor.value;
                        if (val && val.timestamp && (now - val.timestamp > DEFAULT_MAX_AGE_MS)) {
                            cursor.delete();
                        }
                        cursor.continue();
                    }
                };
            } catch (err) {
                // Silencieux
            }
        },

        /**
         * Indique si le navigateur dispose d'une connexion réseau active.
         * @returns {boolean}
         */
        isOnline: function () {
            return typeof navigator !== 'undefined' ? navigator.onLine !== false : true;
        },

        /**
         * Formate un timestamp relatif en français.
         * @param {number} timestamp
         * @returns {string}
         */
        formatTimeAgo: function (timestamp) {
            if (!timestamp) return 'récemment';
            const date = new Date(timestamp);
            const now = new Date();
            const diffMinutes = Math.floor((now - date) / (1000 * 60));

            if (diffMinutes < 1) return "à l'instant";
            if (diffMinutes < 60) return `il y a ${diffMinutes} min`;

            const hours = String(date.getHours()).padStart(2, '0');
            const minutes = String(date.getMinutes()).padStart(2, '0');
            const isToday = date.toDateString() === now.toDateString();

            if (isToday) {
                return `aujourd'hui à ${hours}:${minutes}`;
            }
            const day = String(date.getDate()).padStart(2, '0');
            const month = String(date.getMonth() + 1).padStart(2, '0');
            return `le ${day}/${month} à ${hours}:${minutes}`;
        }
    };

    /**
     * Crée dynamiquement un élément DOM de bannière standardisé (.admin-banner)
     * conforme à la macro Jinja2 admin_banner() du Design System Belle Vitesse.
     * @param {Object} options
     * @param {string} [options.variant='info'] 'warning'|'info'|'success'|'danger'|'neutral'
     * @param {string} [options.icon] Clé d'icône Lucide (ex: 'alert-triangle', 'history', etc.)
     * @param {string} [options.title] Titre en gras
     * @param {string} [options.desc] Description ou texte d'explication
     * @param {string} [options.actionsHtml] HTML des boutons d'actions
     * @param {string} [options.id] ID de l'élément DOM
     * @param {string} [options.className] Classes CSS additionnelles
     * @returns {HTMLElement}
     */
    function createAdminBanner(options) {
        options = options || {};
        const variant = options.variant || 'info';
        const defaultIcons = {
            'warning': 'alert-triangle',
            'info': 'info',
            'success': 'circle-check',
            'danger': 'alert-circle',
            'neutral': 'minus-circle'
        };
        const icon = options.icon || defaultIcons[variant] || 'info';

        const banner = document.createElement('div');
        banner.className = `admin-banner admin-banner--${variant} ${options.className || ''}`.trim();
        if (options.id) banner.id = options.id;
        banner.setAttribute('role', 'alert');

        banner.innerHTML = `
            <div class="admin-banner-content">
                <span class="admin-banner-icon"><i data-lucide="${icon}"></i></span>
                <div class="admin-banner-text">
                    ${options.title ? `<strong class="admin-banner-title">${options.title}</strong>` : ''}
                    ${options.desc ? `<div class="admin-banner-desc">${options.desc}</div>` : ''}
                </div>
            </div>
            ${options.actionsHtml ? `<div class="admin-banner-actions">${options.actionsHtml}</div>` : ''}
        `;
        return banner;
    }

    window.BvDraftStore = BvDraftStore;
    window.createAdminBanner = createAdminBanner;

    // Nettoyage automatique des enregistrements périmés et des soumissions réussies au chargement
    if (typeof window !== 'undefined') {
        setTimeout(() => {
            BvDraftStore.cleanStaleDrafts();
        }, 2000);

        try {
            const cleanPendingDraft = (storageKey, formId) => {
                const pendingKey = sessionStorage.getItem(storageKey);
                if (pendingKey && !document.getElementById(formId)) {
                    BvDraftStore.deleteDraft(pendingKey).catch(() => {});
                    sessionStorage.removeItem(storageKey);
                }
            };
            cleanPendingDraft('bv_pending_inspection_key', 'inspectionForm');
            cleanPendingDraft('bv_pending_incident_key', 'incidentForm');
        } catch (e) {}
    }
})();

