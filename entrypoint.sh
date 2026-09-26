#!/bin/bash
set -e

# ── CSS Bundling ──────────────────────────────────────────────────────
# Génère les bundles CSS au démarrage, APRÈS le montage des volumes.
# Cela garantit que les bundles sont créés à partir des CSS réels
# présents dans /app/static/css (potentiellement montés via un volume).
echo "📦 Génération des bundles CSS..."

if [ -f "scripts/build_bundles.py" ]; then
    python3 scripts/build_bundles.py || {
        echo "⚠️ Échec build_bundles.py, repli sur concaténation manuelle..."
        cat static/css/normalize.css static/css/main.css static/css/slider.css static/css/header.css \
            static/css/footer.css static/css/home.css static/css/categories.css static/css/vehicle.css \
            static/css/grip.css static/css/about-us.css static/css/contact.css static/css/terms-and-conditions.css \
            static/css/animation.css static/css/mouse-scrolling-animation.css static/css/filtersliders.css \
            static/css/newsletter.css > static/css/styles.bundle.css
        grep -v "^@import" static/css/styles.css >> static/css/styles.bundle.css
        cat static/css/admin/admin-base.css static/css/admin/admin-sidebar.css static/css/admin/admin-components.css \
            static/css/admin/admin-login.css static/css/admin/admin-dashboard.css static/css/admin/admin-contacts.css \
            static/css/admin/calendar.css static/css/admin/admin-pricing.css static/css/admin/admin-utilities.css \
            static/css/admin/admin-projects.css static/css/admin/admin-js.css \
            static/css/admin/admin-booking.css static/css/admin/admin-cmdk.css static/css/admin/admin-fleet.css \
            static/css/admin/admin-incidents.css static/css/admin/admin-mcp.css > static/css/admin/admin.bundle.css
    }
else
    cat static/css/normalize.css static/css/main.css static/css/slider.css static/css/header.css \
        static/css/footer.css static/css/home.css static/css/categories.css static/css/vehicle.css \
        static/css/grip.css static/css/about-us.css static/css/contact.css static/css/terms-and-conditions.css \
        static/css/animation.css static/css/mouse-scrolling-animation.css static/css/filtersliders.css \
        static/css/newsletter.css > static/css/styles.bundle.css
    grep -v "^@import" static/css/styles.css >> static/css/styles.bundle.css
    cat static/css/admin/admin-base.css static/css/admin/admin-sidebar.css static/css/admin/admin-components.css \
        static/css/admin/admin-login.css static/css/admin/admin-dashboard.css static/css/admin/admin-contacts.css \
        static/css/admin/calendar.css static/css/admin/admin-pricing.css static/css/admin/admin-utilities.css \
        static/css/admin/admin-projects.css static/css/admin/admin-js.css \
        static/css/admin/admin-booking.css static/css/admin/admin-cmdk.css static/css/admin/admin-fleet.css \
        static/css/admin/admin-incidents.css static/css/admin/admin-mcp.css > static/css/admin/admin.bundle.css
fi

echo "✅ Bundles CSS générés avec succès"

# ── Migration du schéma de base de données ─────────────────────────────
echo "🗄️ Application des migrations de schéma (Flask-Migrate)..."
python3 -c "
from app import create_app
from flask_migrate import upgrade
app = create_app()
with app.app_context():
    upgrade()
" || {
    echo "⚠️ Avertissement lors des migrations Flask-Migrate, exécution du repli..."
    if [ -f "scripts/migrate_kdrive_schema.py" ]; then
        python3 scripts/migrate_kdrive_schema.py || true
    fi
}

# ── Lancement de l'application ────────────────────────────────────────
exec "$@"
