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
    && rm -rf /var/lib/apt/lists/*

# Copier le fichier requirements.txt et installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste du code de l'application
COPY . .

# Exposer le port sur lequel l'application s'exécute
EXPOSE 5001

# Commande pour démarrer l'application avec Gunicorn
# Utilise le fichier de configuration (post_fork, max_requests, etc.)
CMD ["gunicorn", "-c", "gunicorn.conf.py", "--forwarded-allow-ips=*", "app:app"]