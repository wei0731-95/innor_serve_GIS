# syntax=docker/dockerfile:1
# CityGap React frontend：Node build → nginx 靜態伺服 + /api 反向代理到 backend container

# ---------- build stage ----------
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY index.html vite.config.js ./
COPY src ./src

# 前端 API 位址是 Vite build-time 變數（import.meta.env.VITE_API_BASE_URL）。
# Docker 預設空字串 → 瀏覽器呼叫同源 /api/...，由 nginx 轉給 backend container，
# 不需要把宿主機的 host:port 寫進 JS bundle，也不需要跨網域 CORS。
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

# ---------- runtime stage ----------
FROM nginx:1.27-alpine
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
