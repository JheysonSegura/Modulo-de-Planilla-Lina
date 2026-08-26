# Auditoría de seguridad 2026-08-25 (hallazgo B5): tag + digest, no solo
# tag -- reproducible incluso si "3.12-slim" se re-etiqueta con otro
# contenido más adelante. Actualizar el digest a mano cuando se quiera
# tomar una imagen base más nueva (`docker pull python:3.12-slim` y
# copiar el digest resultante).
FROM python:3.12-slim@sha256:7a8b475003c4fe15a2cd4e55e5cfc2f3560bdc9333d624f24cdd6d4340fd7a17

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Dependencias de sistema de WeasyPrint (Fase 16: generación de PDF)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
