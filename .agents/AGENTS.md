# Règles de l'Espace de Travail

- **Messages de Commit Git Systématiques** : Générer systématiquement un message de commit Git détaillé, structuré (format Conventional Commits) et rédigé en français, résumant toutes les modifications effectuées à la fin de chaque tâche ou intervention.
- **Raccourci `--git`** : Si l'utilisateur saisit ou mentionne le mot-clé exact `--git` dans sa requête, l'agent doit exécuter `git status` et/ou `git diff` pour analyser les modifications locales, puis générer un message de commit Git structuré (format Conventional Commits), détaillé et rédigé en français.
- **Proscription des styles inlines (CSS externe obligatoire)** : Ne jamais utiliser d'attributs `style="..."` dans les templates HTML (sauf contrainte technique absolue telle que les corps d'e-mails HTML). Toujours déporter le CSS dans des fichiers `.css` dédiés (ou exploiter les classes utilitaires existantes) afin de garantir un code propre, modulaire et maintenable.


