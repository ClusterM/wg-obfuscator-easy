# ---
# Container with WireGuard Obfuscator binary
# ---
FROM clustermeerkat/wg-obfuscator:1.5 AS obf


# ---
# Container to build backend
# ---
FROM node:22-alpine AS frontend
WORKDIR /app
COPY frontend /app
RUN npm install
RUN npm run build


# ---
# Main container
# ---
FROM debian:trixie-slim

WORKDIR /app
ENV PIP_BREAK_SYSTEM_PACKAGES=1
ENV PIP_ROOT_USER_ACTION=ignore

COPY --from=obf /app/wg-obfuscator /usr/bin/wg-obfuscator
COPY backend /app
COPY --from=frontend /static /app/static

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tini iptables iproute2 procps wireguard python3 python3-pip
RUN rm -rf /var/lib/apt/lists/*

# for debug
#RUN apt-get install -y \
#    iputils-ping curl psmisc net-tools

RUN pip install -r requirements.txt

ENTRYPOINT ["tini", "--", "./docker-entrypoint.sh"]
