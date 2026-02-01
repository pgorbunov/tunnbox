# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npx svelte-kit sync
RUN npm run build

# Stage 2: Build wireguard-go (Userspace implementation)
FROM golang:1.23-alpine AS wg-go-builder
RUN apk add --no-cache git build-base
RUN go install golang.zx2c4.com/wireguard@latest

# Stage 3: Production image
FROM ubuntu:24.04

LABEL maintainer="TunnBox"
LABEL description="Modern web interface for managing WireGuard VPN (TunnBox)"

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wireguard \
    wireguard-tools \
    resolvconf \
    iptables \
    iproute2 \
    python3 \
    python3-pip \
    python3-venv \
    openssl \
    curl \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Set up Python virtual environment
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Install Python dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r backend/requirements.txt

# Copy backend
COPY backend/ ./backend/
COPY backend/tests/ ./backend/tests/

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/frontend/build ./frontend/build

# Copy wireguard userspace implementation from builder stage
COPY --from=wg-go-builder /go/bin/wireguard /usr/bin/wireguard
RUN ln -s /usr/bin/wireguard /usr/bin/wireguard-go

# Copy entrypoint script and fix line endings (Windows CRLF -> Unix LF)
COPY docker-entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

# Mock resolvconf to prevent systemd errors in Docker
RUN echo '#!/bin/sh' > /usr/bin/resolvconf && \
    echo 'exit 0' >> /usr/bin/resolvconf && \
    chmod +x /usr/bin/resolvconf

# Create directories for WireGuard configs and app data
RUN mkdir -p /etc/wireguard /app/data

# Environment variables with defaults
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000
ENV DEBUG=false
ENV DATABASE_URL=sqlite+aiosqlite:////app/data/tunnbox.db
ENV WG_CONFIG_PATH=/etc/wireguard
ENV WG_DEFAULT_DNS=1.1.1.1
ENV ACCESS_TOKEN_EXPIRE_MINUTES=15
ENV REFRESH_TOKEN_EXPIRE_DAYS=7

# Expose ports
# 8000 = Web UI
# 51820 = WireGuard (UDP)
EXPOSE 8000
EXPOSE 51820/udp

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Volumes for persistent data
VOLUME ["/etc/wireguard", "/app/data"]

ENTRYPOINT ["/entrypoint.sh"]
