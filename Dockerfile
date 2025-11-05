# ---
# Container with WireGuard Obfuscator binary
# ---
FROM clustermeerkat/wg-obfuscator:1.5 AS obf


# ---
# Main container
# ---
FROM debian:trixie-slim

WORKDIR /app
ENV PIP_BREAK_SYSTEM_PACKAGES=1
ENV PIP_ROOT_USER_ACTION=ignore

COPY --from=obf /app/wg-obfuscator /usr/bin/wg-obfuscator
COPY backend /app
# Copy pre-built frontend static files (built outside Docker)
COPY static /app/static

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tini iptables iproute2 procps wireguard python3 python3-pip python3-packaging && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get purge -y python3-pip python3-wheel && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /tmp/* /var/tmp/* && \
    find /usr/lib/python3* -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true && \
    find /usr/lib/python3* -type f -name "*.pyc" -delete 2>/dev/null || true && \
    find /usr/lib/python3* -type f -name "*.pyo" -delete 2>/dev/null || true

# for debug
#RUN apt-get install -y \
#    iputils-ping curl psmisc net-tools

ENTRYPOINT ["tini", "--", "./docker-entrypoint.sh"]
