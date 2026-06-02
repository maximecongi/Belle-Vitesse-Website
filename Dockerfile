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

# Copier et rendre exécutable le script d'entrypoint
# Le bundling CSS est effectué au démarrage (et non au build)
# car le volume Docker écrase /app/static au runtime.
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Exposer le port sur lequel l'application s'exécute
EXPOSE 5001

# Healthcheck pour le conteneur (Fix #17)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5001/health || exit 1

# Entrypoint : génère les bundles CSS puis lance la commande
ENTRYPOINT ["./entrypoint.sh"]

# Commande pour démarrer l'application avec Gunicorn
# Utilise le fichier de configuration (post_fork, max_requests, etc.)
CMD ["gunicorn", "-c", "gunicorn.conf.py", "--forwarded-allow-ips=*", "app:app"]