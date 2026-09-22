# Règles de l'Espace de Travail

- **Messages de Commit Git Systématiques** : Générer systématiquement un message de commit Git détaillé, structuré (format Conventional Commits) et rédigé en français, résumant toutes les modifications effectuées à la fin de chaque tâche ou intervention.
- **Raccourci `--git`** : Si l'utilisateur saisit ou mentionne le mot-clé exact `--git` dans sa requête, l'agent doit exécuter `git status` et/ou `git diff` pour analyser les modifications locales, puis générer un message de commit Git structuré (format Conventional Commits), détaillé et rédigé en français.
- **Proscription des styles inlines (CSS externe obligatoire)** : Ne jamais utiliser d'attributs `style="..."` dans les templates HTML (sauf contrainte technique absolue telle que les corps d'e-mails HTML). Toujours déporter le CSS dans des fichiers `.css` dédiés (ou exploiter les classes utilitaires existantes) afin de garantir un code propre, modulaire et maintenable.
- **Système de Couleurs & Cohérence des Entités Métier (Design System Belle Vitesse)** :
  - Respecter scrupuleusement la nomenclature et la palette sémantique du Design System sur l'ensemble du site (admin ERP et portails publics de signature) :
    * **Check-in (Retours)** : Bleu Océan (`--entity-checkin`: `#3B82F6`, bg: `#DBEAFE`, text: `#1E40AF`, icône Lucide: `package-check`).
    * **Check-out (Départs)** : Vert Émeraude (`--entity-checkout`: `#10B981`, bg: `#D1FAE5`, text: `#065F46`, icône Lucide: `truck`).
    * **Tournages / Projets** : Ambre Chaud (`--entity-project`: `#F59E0B`, bg: `#FEF3C7`, text: `#B45309`, icône Lucide: `clapperboard`).
    * **Incidents / Dommages** : Rouge Carmin (`--entity-incident`: `#EF4444`, bg: `#FEE2E2`, text: `#991B1B`, icône Lucide: `wrench` / `alert-triangle`).
    * **Décharges (Waivers)** : Violet / Indigo (`--entity-waiver`: `#8B5CF6`, bg: `#EDE9FE`, text: `#5B21B6`, icône Lucide: `file-signature` / `shield`).
    * **Statuts transversaux** : Succès/Validé (`--status-success`: `#10B981`, bg: `#D1FAE5`, text: `#065F46`, icône Lucide: `circle-check`), Attention/Attente (`--status-warning`: `#D97706`), Danger/Critique (`--status-danger`: `#EF4444`), Info/À venir (`--status-info`: `#0284C7`), Neutre/Archivé (`--status-neutral`: `#64748B`).
  - **Cohérence des composants et utilitaires** :
    * Pour une même entité ou statut, synchroniser systématiquement la couleur du badge (`badge-pill`), de l'icône Lucide, de la puce de timeline, de la bordure (`.u-border-left-*`, `.u-border-*`) et des cartes KPI.
    * Ne jamais coder de couleurs hexadécimales en dur pour ces entités dans le HTML ou les styles spécifiques : toujours consommer les variables CSS `--entity-*` et `--status-*` ou les classes utilitaires dédiées (`.u-text-*`, `.u-bg-*`, `.u-bg-*-light`, `.u-border-left-*`).
    * Après toute modification de fichiers CSS, régénérer systématiquement les bundles avec `python3 scripts/build_bundles.py --force`.
- **Exclusion et masquage des pré-devis** : La section et les fonctionnalités de pré-devis / devis (`pre_quotes`) sont désactivées et masquées de l'interface utilisateur. Ne plus les prendre en compte, ne pas les afficher dans les vues (projets, hubs, listes), et ne pas chercher à les intégrer ou les étendre dans les futures implémentations de fonctionnalités.



