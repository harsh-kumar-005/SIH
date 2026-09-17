# =============================================================================
# Egreen-Quanta Frontend Production Dockerfile (Multi-Stage)
# =============================================================================

# --- Stage 1: Build static assets ---
FROM node:20-alpine AS build

WORKDIR /app

# Copy package manifests and install dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy source code and build config
COPY . .

# Optional build-time argument for custom backend URL
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

# Build production bundle
RUN npm run build

# --- Stage 2: Serve with Nginx ---
FROM nginx:1.25-alpine AS runner

# Remove default nginx html
RUN rm -rf /usr/share/nginx/html/*

# Copy built static assets from builder stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose HTTP port
EXPOSE 80

# Run nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
