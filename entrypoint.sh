#!/bin/bash
set -e

# ── CSS Bundling ──────────────────────────────────────────────────────
# Génère les bundles CSS au démarrage, APRÈS le montage des volumes.
# Cela garantit que les bundles sont créés à partir des CSS réels
# présents dans /app/static/css (potentiellement montés via un volume).
echo "📦 Génération des bundles CSS..."

cat static/css/normalize.css \
    static/css/main.css \
    static/css/slider.css \
    static/css/header.css \
    static/css/footer.css \
    static/css/home.css \
    static/css/categories.css \
    static/css/vehicle.css \
    static/css/grip.css \
    static/css/about-us.css \
    static/css/contact.css \
    static/css/terms-and-conditions.css \
    static/css/animation.css \
    static/css/mouse-scrolling-animation.css \
    static/css/filtersliders.css \
    static/css/newsletter.css \
    > static/css/styles.bundle.css

# Ajouter le contenu de styles.css en filtrant les lignes @import pour éviter d'invalider le CSS
grep -v "^@import" static/css/styles.css >> static/css/styles.bundle.css

cat static/css/admin/admin-base.css \
    static/css/admin/admin-sidebar.css \
    static/css/admin/admin-components.css \
    static/css/admin/admin-login.css \
    static/css/admin/admin-dashboard.css \
    static/css/admin/admin-contacts.css \
    static/css/admin/calendar.css \
    static/css/admin/admin-pricing.css \
    static/css/admin/admin-utilities.css \
    static/css/admin/admin-projects.css \
    static/css/admin/prequote.css \
    static/css/admin/admin-js.css \
    static/css/admin/admin-booking.css \
    > static/css/admin/admin.bundle.css

echo "✅ Bundles CSS générés avec succès"

# ── Lancement de l'application ────────────────────────────────────────
exec "$@"
