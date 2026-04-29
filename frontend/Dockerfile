# Frontend Dockerfile - AI Test Platform
FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

# Nginx config for SPA routing
RUN echo 'server { \
    listen 8010; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { try_files $uri /index.html; } \
    location /api { proxy_pass http://backend:8020; } \
    location /ws { proxy_pass http://backend:8020; proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; } \
    }' > /etc/nginx/conf.d/default.conf

EXPOSE 8010

CMD ["nginx", "-g", "daemon off;"]
