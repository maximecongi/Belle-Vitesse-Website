# Utiliser une image Python officielle comme base
FROM python:3.14-slim

# Définir le répertoire de travail dans le conteneur
WORKDIR /app

# Installer les dépendances système nécessaires
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    default-mysql-client \
    build-essential \
    pkg-config \
    libffi-dev \
    libssl-dev \
    python3-dev \
    libgobject-2.0-0 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    fonts-liberation \
    fonts-dejavu-core \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copier le fichier requirements.txt et installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste du code de l'application
COPY . .

# Concaténer les CSS pour la production (Fix #9)
RUN cat static/css/normalize.css \
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

RUN cat static/css/admin/admin-base.css \
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

# Exposer le port sur lequel l'application s'exécute
EXPOSE 5001

# Healthcheck pour le conteneur (Fix #17)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5001/health || exit 1

# Commande pour démarrer l'application avec Gunicorn
# Utilise le fichier de configuration (post_fork, max_requests, etc.)
CMD ["gunicorn", "-c", "gunicorn.conf.py", "--forwarded-allow-ips=*", "app:app"]