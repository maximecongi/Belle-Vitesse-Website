# -------- Base image --------
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app


# -------- Builder stage --------
FROM base AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libmariadb-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --user --no-cache-dir -r requirements.txt


# -------- Runtime stage --------
FROM base AS runtime

# Installer uniquement les libs runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmariadb3 \
    && rm -rf /var/lib/apt/lists/*

# Copier dépendances python compilées
COPY --from=builder /root/.local /root/.local

ENV PATH=/root/.local/bin:$PATH

# Copier application
COPY . .

# Créer utilisateur non-root
RUN useradd -m appuser
USER appuser

EXPOSE 5000

CMD ["gunicorn", \
     "--workers", "3", \
     "--threads", "2", \
     "--timeout", "120", \
     "--bind", "0.0.0.0:5000", \
     "run:app"]
