/**
 * static/js/src/admin/meeting-report.js
 * Module de mise en page temps réel et d'export PDF de comptes-rendus de réunion Belle Vitesse.
 */

const BV_SAMPLE_MEETING_REPORT = `# BV - Véhicules et sécurité : risk assessments, convoyage, et tarification

Thu, 05 Nov 26

## Risk Assessment et Documents Légaux

- Corpus de textes légaux et risk assessments à finaliser avant fin d’année
- Base actuelle jugée solide, mais à renvoyer aux avocats pour validation
- Documents à faire signer identifiés : CGL, risk assessment, règles de sécurité
  - Attestation pilote à fusionner dans les règles de sécurité (avec coche spécifique “non-salarié BV”)
  - Pilotes signent à chaque film (pas annuellement) pour éviter les problèmes d’excès de pouvoir
  - Règles de sécurité signées par : Dir Prod, chef machiniste, pilote, 1er assistant réel
- Risk assessments à envoyer avec les call sheets, signés par les responsables concernés
- Documents à watermarker : le risk assessment de 8 pages est un argument de vente différenciant
  - À terme : version bilingue FR/EN pour les tournages avec chefs-op étrangers
- Objectif semaine prochaine : envoyer les PDF (avec faux noms) aux avocats pour retour

## Convoyage sur Route Ouverte : Ligne Rouge Juridique

- Convoi sur route ouverte = risque majeur identifié dans le risk assessment
  - Véhicules non homologués sur voie publique : position ferme, BV ne peut pas cautionner
  - Responsabilité en cascade : assurance prod, pilote, puis loueur si complicité établie
- Sur Pumpkin Black : convois jusqu’à 12 km, pratique quasi-quotidienne imposée par la prod
- Équipement de balisage (gyrophare, gilets, triangles) fourni pour contextes légaux uniquement, jamais pour convoyage
- Solution envisagée : remorque tractée par un véhicule homologué
  - Véhicule tiré = plus considéré sur voie publique, convoi exceptionnel possible
  - Nécessite un permis spécifique
  - Passage du permis remorque pour tous les pilotes et techniciens à planifier
  - Premiers pilotes (Sacha, Ewen, Maxime) : formation facilitée par BV ; ensuite, critère de recrutement obligatoire

## Améliorations Opérationnelles : Polaris et Véhicules

- Retour d’expérience Pumpkin Black sur le Polaris :
  - Suspensions trop molles + surcharge à l’arrière : frottement des plateformes au sol
  - Répartition correcte : 2 personnes à l’arrière, 1 dans la cabine en plus du pilote
  - Fourche moto : joints fuyants après stockage prolongé, corrigé
  - Black Arm + rallonge à l’arrière : déséquilibre résolu en retirant la rallonge
- Priorité absolue avant fin novembre : protection des planchers et zones de contact
  - Pare-chocs caoutchouc à insérer dans les tubes 50 pour casser les angles coupants
  - Mousses antichoc (type Dyma) sur toute la longueur des planchers, fixées velcro
  - Applicable sur Polaris en premier, puis e-car et vélos (version miniature)
- Roue avant : protection à concevoir (contrainte de braquage importante)
- Lève-charge lourd (heavy duty) identifié comme besoin urgent
  - 2 options : un heavy duty (~50K) pour grosses configs, un léger (~10K) pour petites
  - Premier achat prioritaire de l’année

## Formation et Cascade

- Objectif : sessions de formation circuit avant fin d’année pour Ewen et Maxime
  - Certificats et formations reconnues nécessaires pour crédibiliser les pilotes sur cascades
  - Contact possible : Tanguy (cascade moto) pour identifier des formations homologuées
  - Deadline : 5 janvier pour la journée moto Paris 18 (scène accident scooter avec Titan)
- Ewen à entraîner avec la Titan sur la moto avant Paris 18 (tête plus lourde, whip pan plus fort)
- Formule moto recommandée : Ewen (pilote) + Maxime (tête), unité polyvalente qui s’assiste mutuellement
- Pilotes externes : privilégier des profils validés par BV
  - Tanguy : profil idéal (discret, concentré, passionné) ; Jérémy : compétent techniquement, relationnel insuffisant
  - Cédric Close (cascadeur) a manifesté son intérêt pour piloter

## Tarification et Négociation

- Problème Sacha / KeepFun : alignement involontaire sur un forfait sans majoration heures sup ni nuit
  - Nécessité de former les pilotes aux méthodes de négociation pour ne pas casser les prix
  - Une mauvaise négo sur un film crée un précédent difficile à corriger sur les suivants
- Positionnement tarifaire actuel : remise de 30% sur véhicules BV, 20% sur véhicules prestataires
  - Pumping Black semaine 1 : 5 640 € HT ; semaine 2 : 7 700 € ; semaine 3 : 6 100 € ; Paris : ~7 000 €
  - Paris 18 (4 jours) : 4 503 € HT
  - Total Pumping Black estimé ~20-24K€ net BV (après déduction camions RVZ et Maxime)
- Les prods comprennent la valeur du service, mais ne l’anticipent pas dans leur budget
  - Dépense non anticipée : le technicien véhicule en plus du pilote (surtout sur les vélos)
  - 80% des négos aboutissent ; les vélos restent les plus difficiles à vendre
- Stratégie commerciale : garder la négociation en interne, déléguer uniquement l’édition des devis/factures à terme
  - Risque de déléguer trop tôt : perte de l’identité passionnée qui fait vendre

## Pilote + Technicien : Flexibilité de l’Offre

- Règle absolue : la moto ne sort jamais seule (toujours pilote + technicien tête)
- Pour les autres véhicules : offre modulable selon la manutention demandée
  - Gros tournage / grosse manutention → pilote + technicien véhicule
  - Petit plan pub simple → pilote seul possible si chef machiniste compétent sur place
- Objectif : montrer qu’on s’adapte au projet, pas une méthodologie rigide
  - Exemple : un suivi latéral Black Arm en pub de running ne justifie pas deux personnes

## Prochains Tournages

- Nike (lundi-mardi) : vélos en circulation ouverte
  - Lumières, catadioptres à ajouter avant lundi pour Sacha
  - Marie Allègre (prod) informée des conditions de sécurité, accord obtenu
- Paris 18 : journée moto (accident scooter), Titan sur la moto, entraînement nécessaire en amont
- Sentinelle saison 2 (Sylvain Chaud, chef-op Alain Duplantier) : vélo dans une coursive d’hôpital désaffecté
  - Sol bétonné avec creux, à évaluer ; courant janvier
  - Séquences en tranchées (Belgique) : fin janvier à mi-mars, Polaris et moto envisagés
- Biopic (Fabio) : prépa en cours depuis novembre, véhicules ponctuels (pas un rolling pur)
  - e-kart particulièrement adapté pour les séquences de dialogue en mouvement
  - Specs e-kart à définir rapidement, financement partiel via revenus Pumping Black

## Administratif et Trésorerie

- SIRET déclaré et en ligne ; TVA à vérifier
- RIB compte courant en attente pour facturer Pumping Black
- Trésorerie cible : maintenir un minimum de 40-50K€ de réserve
  - Polaris : ~60K€ à rembourser à RVZ ; stratégie d’assigner ~10% de chaque projet au remboursement
- Remorque moto : envisager de la sortir du local pour récupérer de l’espace
  - Déplacer la grille vers l’extérieur : gain estimé de ~2 mètres, stockage remorque + matière première
  - Étagères en hauteur au-dessus des établis à prévoir
- Réunion admin à planifier avec tous les associés : facturation, devis, logiciel, ouverture de boîte
- Mot de passe du site à renvoyer pour accès aux tournages et véhicules

## Prochaines Étapes

- **Watermarker les documents risk assessment** (Maxime)
- **Finaliser et envoyer les PDF légaux aux avocats** (Maxime)
- **Ajouter lumières et catadioptres sur les vélos avant lundi**
- **Rechercher formations cascade moto homologuées**
- **Définir les specs précises du e-kart**
- **Renvoyer le mot de passe du site** (Maxime)
- **Tester les solutions de pare-chocs et mousses à l'atelier**`;

function initMeetingReport() {
    const mdInput = document.getElementById('meeting-md-input');
    if (!mdInput) return;

    const inputRef = document.getElementById('meeting-meta-ref');
    const inputDate = document.getElementById('meeting-meta-date');
    const inputDocType = document.getElementById('meeting-meta-doctype');

    const previewSheet = document.getElementById('meeting-sheet-content');
    const previewHeaderTitle = document.getElementById('preview-header-title');
    const previewHeaderRef = document.getElementById('preview-header-ref');
    const previewHeaderDate = document.getElementById('preview-header-date');
    const previewMainTitle = document.getElementById('preview-main-title');
    const previewFooterRef = document.getElementById('preview-footer-ref');

    const btnLoadSample = document.getElementById('meeting-btn-sample');
    const btnClear = document.getElementById('meeting-btn-clear');
    const btnCopyHtml = document.getElementById('meeting-btn-copy');
    const btnDownloadPdf = document.getElementById('meeting-btn-download-pdf');
    const btnPrint = document.getElementById('meeting-btn-print');
    const draftStatus = document.getElementById('meeting-draft-status');

    let debounceTimer = null;
    let userEditedRef = false;
    let userEditedDate = false;

    const STORAGE_KEY = 'bv_meeting_report_draft';

    // 1. Détection intelligente de la date et de l'ID format BVMR-JJMMAAAA
    const MONTHS_MAP = {
        jan: '01', feb: '02', mar: '03', apr: '04', may: '05', jun: '06',
        jul: '07', aug: '08', sep: '09', oct: '10', nov: '11', dec: '12',
        janv: '01', févr: '02', fevr: '02', avr: '04', mai: '05', juin: '06',
        juil: '07', août: '08', aout: '08', sept: '09', oct: '10', nov: '11', déc: '12', dec: '12',
        janvier: '01', février: '02', fevrier: '02', mars: '03', avril: '04',
        juillet: '07', septembre: '09', octobre: '10', novembre: '11', décembre: '12', decembre: '12'
    };

    function parseMeetingDate(rawDate) {
        const now = new Date();
        const dd = String(now.getDate()).padStart(2, '0');
        const mm = String(now.getMonth() + 1).padStart(2, '0');
        const yyyy = now.getFullYear();
        const defaultId = `BVMR-${dd}${mm}${yyyy}`;
        const defaultDisplay = `${dd}/${mm}/${yyyy}`;
        const defaultIso = `${yyyy}-${mm}-${dd}`;

        if (!rawDate || !rawDate.trim()) {
            return { display: defaultDisplay, id: defaultId, iso: defaultIso };
        }

        const s = rawDate.trim();

        // 1. Format ISO YYYY-MM-DD (valeur native de l'input type="date")
        const isoMatch = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
        if (isoMatch) {
            const y = isoMatch[1];
            const m = isoMatch[2];
            const d = isoMatch[3];
            return { display: `${d}/${m}/${y}`, id: `BVMR-${d}${m}${y}`, iso: s };
        }

        // 2. 05/11/2026 ou 05-11-2026
        const slashMatch = s.match(/^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$/);
        if (slashMatch) {
            const d = slashMatch[1].padStart(2, '0');
            const m = slashMatch[2].padStart(2, '0');
            let y = slashMatch[3];
            if (y.length === 2) y = '20' + y;
            return { display: `${d}/${m}/${y}`, id: `BVMR-${d}${m}${y}`, iso: `${y}-${m}-${d}` };
        }

        // 3. Thu, 05 Nov 26 ou 5 novembre 2026
        const textMatch = s.match(/(\d{1,2})\s+([a-zA-Z\u00C0-\u017F\.]+)\s+(\d{2,4})/);
        if (textMatch) {
            const d = textMatch[1].padStart(2, '0');
            const moStr = textMatch[2].toLowerCase().replace('.', '');
            let y = textMatch[3];
            if (y.length === 2) y = '20' + y;
            const m = MONTHS_MAP[moStr];
            if (m) {
                return { display: `${d}/${m}/${y}`, id: `BVMR-${d}${m}${y}`, iso: `${y}-${m}-${d}` };
            }
        }

        return { display: s, id: defaultId, iso: defaultIso };
    }

    // 2. Parser Markdown robuste avec puces hiérarchiques et carré or .dot-before
    function parseMarkdownToHtml(mdText) {
        const lines = mdText.split('\n');
        let html = [];
        let listStack = [];
        let sectionCounter = 0;

        function closeAllLists() {
            while (listStack.length > 0) {
                html.push('</li></ul>');
                listStack.pop();
            }
        }

        function formatInline(str) {
            const reBold = new RegExp('\\u002A\\u002A(.+?)\\u002A\\u002A', 'g');
            const reItalic = new RegExp('\\u002A(.+?)\\u002A', 'g');
            return str
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(reBold, '<strong>$1</strong>')
                .replace(reItalic, '<em>$1</em>')
                .replace(/`([^`]+)`/g, '<code>$1</code>');
        }

        let extractedTitle = '';
        let extractedDate = '';
        let foundTitle = false;
        let foundDate = false;

        for (let i = 0; i < lines.length; i++) {
            const rawLine = lines[i];
            const trimmed = rawLine.trim();

            if (!foundTitle && trimmed.startsWith('# ')) {
                extractedTitle = trimmed.substring(2).trim();
                foundTitle = true;
                continue;
            }

            if (foundTitle && !foundDate && trimmed && !trimmed.startsWith('#') && !trimmed.startsWith('-') && !trimmed.startsWith('*') && !trimmed.startsWith('>') && trimmed.length < 80) {
                extractedDate = trimmed;
                foundDate = true;
                continue;
            }

            if (!trimmed) {
                continue;
            }

            // H2 -> Titre officiel Belle Vitesse numéroté 1., 2., 3. avec carré or .dot-before
            if (trimmed.startsWith('## ')) {
                closeAllLists();
                sectionCounter++;
                let text = trimmed.substring(3).trim();
                // Nettoyer toute numérotation manuelle pré-existante (ex: "1. ", "1 - ")
                text = text.replace(new RegExp('^\\d+[.\\-\\)]\\s*'), '');
                html.push('<h2 class="cgl-section-title pdf-section-title dot-before"><span class="section-num">' + sectionCounter + '. </span>' + formatInline(text) + '</h2>');
                continue;
            }

            // H3 -> Sous-section
            if (trimmed.startsWith('### ')) {
                closeAllLists();
                const text = trimmed.substring(4).trim();
                html.push('<h3 class="cgl-subtitle pdf-subtitle">' + formatInline(text) + '</h3>');
                continue;
            }

            // Citations / Notes blockquote
            if (trimmed.startsWith('> ')) {
                closeAllLists();
                const text = trimmed.substring(2).trim();
                html.push('<div class="pdf-context-box">' + formatInline(text) + '</div>');
                continue;
            }

            // Séparateur horizontal
            if (trimmed === '---' || trimmed === '***') {
                closeAllLists();
                html.push('<hr>');
                continue;
            }

            // Listes à puces
            const listMatch = rawLine.match(/^(\s*)([-*+]|\d+\.)\s+(.*)$/);
            if (listMatch) {
                const indentSpaces = listMatch[1].length;
                const content = formatInline(listMatch[3].trim());
                const level = Math.max(0, Math.floor(indentSpaces / 2));

                if (listStack.length === 0) {
                    html.push('<ul class="pdf-bullets-list">');
                    listStack.push(0);
                    html.push('<li>' + content);
                } else {
                    const currentLevel = listStack.length - 1;
                    if (level > currentLevel) {
                        html.push('<ul>');
                        listStack.push(level);
                        html.push('<li>' + content);
                    } else if (level < currentLevel) {
                        while (listStack.length - 1 > level) {
                            html.push('</li></ul>');
                            listStack.pop();
                        }
                        html.push('</li><li>' + content);
                    } else {
                        html.push('</li><li>' + content);
                    }
                }
                continue;
            }

            // Paragraphe classique
            closeAllLists();
            html.push('<p>' + formatInline(trimmed) + '</p>');
        }

        closeAllLists();

        return {
            title: extractedTitle,
            dateRaw: extractedDate,
            htmlBody: html.join('\n')
        };
    }

    // 3. Mise à jour de l'aperçu et sauvegarde LocalStorage
    function updatePreview() {
        const mdText = mdInput.value || '';
        const parsed = parseMarkdownToHtml(mdText);

        const dateResult = parseMeetingDate(userEditedDate && inputDate.value ? inputDate.value : parsed.dateRaw);

        if (!userEditedDate && dateResult.iso) {
            inputDate.value = dateResult.iso;
        }

        if (!userEditedRef) {
            inputRef.value = dateResult.id;
        }

        const currentTitle = parsed.title || 'Compte-Rendu de Réunion';
        const currentRef = inputRef.value.trim() || dateResult.id;
        const currentDate = dateResult.display;
        const currentDocType = (inputDocType.value || 'COMPTE RENDU DE RÉUNION').trim();

        if (previewMainTitle) previewMainTitle.textContent = currentTitle;
        if (previewHeaderTitle) previewHeaderTitle.textContent = currentDocType;
        if (previewHeaderRef) previewHeaderRef.textContent = currentRef;
        if (previewFooterRef) previewFooterRef.textContent = currentRef;
        if (previewHeaderDate) previewHeaderDate.textContent = currentDate;

        if (previewSheet) {
            previewSheet.innerHTML = parsed.htmlBody;
        }

        // Sauvegarde LocalStorage
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({
                markdown: mdText,
                ref: userEditedRef ? inputRef.value : '',
                date: userEditedDate ? inputDate.value : '',
                docType: inputDocType.value
            }));
            if (draftStatus) {
                draftStatus.textContent = 'Brouillon sauvegardé';
            }
        } catch (e) {
            // Ignorer si quota ou navigation privée
        }
    }

    function scheduleUpdate() {
        if (debounceTimer) clearTimeout(debounceTimer);
        debounceTimer = setTimeout(updatePreview, 120);
    }

    // Écouteurs sur les entrées
    mdInput.addEventListener('input', () => {
        scheduleUpdate();
    });

    if (inputRef) {
        inputRef.addEventListener('input', () => {
            userEditedRef = true;
            scheduleUpdate();
        });
    }

    if (inputDate) {
        const onDateChanged = () => {
            userEditedDate = true;
            if (inputDate.value) {
                const res = parseMeetingDate(inputDate.value);
                if (!userEditedRef) {
                    inputRef.value = res.id;
                }
            }
            scheduleUpdate();
        };
        inputDate.addEventListener('input', onDateChanged);
        inputDate.addEventListener('change', onDateChanged);
    }

    if (inputDocType) {
        inputDocType.addEventListener('input', () => {
            scheduleUpdate();
        });
    }

    // Bouton Charger l'Exemple
    if (btnLoadSample) {
        btnLoadSample.addEventListener('click', () => {
            mdInput.value = BV_SAMPLE_MEETING_REPORT;
            userEditedRef = false;
            userEditedDate = false;
            updatePreview();
        });
    }

    // Bouton Effacer
    if (btnClear) {
        btnClear.addEventListener('click', async () => {
            if (await window.adminConfirm('Réinitialiser le compte-rendu ? Le texte saisi sera effacé.', { label: 'Réinitialiser' })) {
                mdInput.value = '';
                userEditedRef = false;
                userEditedDate = false;
                try {
                    localStorage.removeItem(STORAGE_KEY);
                } catch (e) { }
                updatePreview();
            }
        });
    }

    // Bouton Copier le HTML
    if (btnCopyHtml) {
        btnCopyHtml.addEventListener('click', () => {
            if (previewSheet) {
                navigator.clipboard.writeText(previewSheet.innerHTML).then(() => {
                    const origText = btnCopyHtml.textContent;
                    btnCopyHtml.textContent = '✓ HTML Copié !';
                    setTimeout(() => {
                        btnCopyHtml.textContent = origText;
                    }, 2000);
                });
            }
        });
    }

    // Bouton Télécharger PDF WeasyPrint
    if (btnDownloadPdf) {
        btnDownloadPdf.addEventListener('click', async () => {
            const mdText = mdInput.value || '';
            if (!mdText.trim()) {
                alert('Veuillez saisir ou coller le contenu du compte-rendu.');
                return;
            }

            btnDownloadPdf.classList.add('admin-btn-loading');
            const origLabel = btnDownloadPdf.innerHTML;
            btnDownloadPdf.innerHTML = `
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="u-spin">
                    <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
                    <path d="M12 2a10 10 0 0 1 10 10"></path>
                </svg>
                <span>Génération...</span>
            `;

            try {
                const dateVal = inputDate && inputDate.value ? parseMeetingDate(inputDate.value).display : '';
                const payload = {
                    markdown: mdText,
                    ref: inputRef ? inputRef.value.trim() : '',
                    date_str: dateVal,
                    doc_type: inputDocType ? inputDocType.value.trim() : ''
                };

                const csrfMeta = document.querySelector('meta[name="csrf-token"]');
                const csrfInput = document.querySelector('input[name="csrf_token"]');
                const csrfToken = (csrfMeta && csrfMeta.getAttribute('content')) || (csrfInput && csrfInput.value) || '';

                const headers = {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                };
                if (csrfToken) {
                    headers['X-CSRFToken'] = csrfToken;
                }

                const response = await fetch('/admin/tools/meeting-report/pdf', {
                    method: 'POST',
                    headers: headers,
                    body: JSON.stringify(payload)
                });

                if (!response.ok) {
                    let errDetail = 'Erreur ' + response.status;
                    try {
                        const errJson = await response.json();
                        if (errJson && errJson.message) errDetail = errJson.message;
                    } catch (e) { }
                    throw new Error(errDetail);
                }

                const blob = await response.blob();
                const downloadUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = downloadUrl;
                const filename = (inputRef ? inputRef.value.trim() : 'BVMR') + '.pdf';
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(downloadUrl);
            } catch (err) {
                console.error('Erreur PDF:', err);
                alert('Impossible de compiler le PDF. Vérifiez votre texte ou rechargez la page.');
            } finally {
                btnDownloadPdf.classList.remove('admin-btn-loading');
                btnDownloadPdf.innerHTML = origLabel;
                if (window.lucide && typeof window.lucide.createIcons === 'function') {
                    window.lucide.createIcons();
                }
            }
        });
    }

    // Restauration initiale depuis localStorage ou chargement de l'exemple si vide
    try {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
            const data = JSON.parse(saved);
            if (data.markdown) {
                mdInput.value = data.markdown;
            } else {
                mdInput.value = BV_SAMPLE_MEETING_REPORT;
            }
            if (data.ref && inputRef) {
                inputRef.value = data.ref;
                userEditedRef = true;
            }
            if (data.date && inputDate) {
                const res = parseMeetingDate(data.date);
                inputDate.value = res.iso;
                userEditedDate = true;
            }
            if (data.docType && inputDocType) {
                inputDocType.value = data.docType;
            }
        } else {
            mdInput.value = BV_SAMPLE_MEETING_REPORT;
        }
    } catch (e) {
        mdInput.value = BV_SAMPLE_MEETING_REPORT;
    }

    updatePreview();

    if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
    }
}

// Initialisation globale
window.initMeetingReport = initMeetingReport;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMeetingReport);
} else {
    initMeetingReport();
}

document.addEventListener('swup:contentReplaced', initMeetingReport);
