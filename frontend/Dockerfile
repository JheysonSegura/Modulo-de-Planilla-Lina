# Auditoría de seguridad 2026-08-25 (hallazgo B5): tag + digest, no solo
# tag -- reproducible incluso si "22-alpine" se re-etiqueta con otro
# contenido más adelante. Actualizar el digest a mano cuando se quiera
# tomar una imagen base más nueva (`docker pull node:22-alpine` y copiar
# el digest resultante).
FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]
