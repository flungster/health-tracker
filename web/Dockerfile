# Build stage: compile the React app.
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# Runtime stage: nginx serves the static bundle and proxies /api to the API.
FROM nginx:1.27-alpine
# nginx's upload body cap mirrors the API's MAX_UPLOAD_MB (same .env value);
# it is a backstop — the API produces the detailed error for real uploads.
ARG MAX_UPLOAD_MB=50
COPY nginx.conf.template /tmp/nginx.conf.template
RUN sed "s/__MAX_UPLOAD_MB__/${MAX_UPLOAD_MB}/g" /tmp/nginx.conf.template \
        > /etc/nginx/conf.d/default.conf \
    && rm /tmp/nginx.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
