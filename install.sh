#!/bin/bash
#
# WireGuard Obfuscator Easy - Installation Script
#
# This script automatically installs and configures WireGuard Obfuscator Easy on a VPS.
# It will:
# 1. Check for root privileges
# 2. Install Docker and required packages
# 3. Detect server IP address
# 4. Generate a domain using nip.io
# 5. Generate random configuration (admin password, web prefix, ports)
# 6. Install and run the Docker container
# 7. Configure Caddy for HTTPS with automatic SSL certificates
# 8. Display access information and credentials
#
# Usage: bash <(curl -Ls https://raw.githubusercontent.com/clustermeerkat/wg-obfuscator-easy/master/install.sh)
#        or: sudo bash install.sh
#

set -e

# Trap to handle errors (only for critical failures)
trap 'print_error "Installation failed at line $LINENO. Please check the error messages above."' ERR INT TERM

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="clustermeerkat/wg-obf-easy:latest"
CONTAINER_NAME="wg-obf-easy"
# Use root's home directory for config (since we run as root)
CONFIG_DIR="/root/.wg-obf-easy"

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to detect OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        OS_VERSION=$VERSION_ID
    elif [ -f /etc/debian_version ]; then
        OS="debian"
        OS_VERSION=$(cat /etc/debian_version)
    elif [ -f /etc/redhat-release ]; then
        OS="rhel"
        OS_VERSION=$(cat /etc/redhat-release)
    else
        OS="unknown"
    fi
}

# Function to install curl
install_curl() {
    print_info "Installing curl..."
    if [ "$OS" = "debian" ] || [ "$OS" = "ubuntu" ]; then
        apt-get update -qq
        apt-get install -y curl
    elif [ "$OS" = "rhel" ] || [ "$OS" = "centos" ] || [ "$OS" = "fedora" ]; then
        if command_exists dnf; then
            dnf install -y curl
        else
            yum install -y curl
        fi
    elif [ "$OS" = "alpine" ]; then
        apk add --no-cache curl
    else
        print_error "Unable to detect OS for curl installation"
        exit 1
    fi
}

# Function to install Docker
install_docker() {
    if command_exists docker; then
        print_info "Docker is already installed"
        return
    fi

    print_info "Installing Docker..."
    
    if [ "$OS" = "debian" ] || [ "$OS" = "ubuntu" ]; then
        # Install Docker using official script
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        rm get-docker.sh
    elif [ "$OS" = "rhel" ] || [ "$OS" = "centos" ] || [ "$OS" = "fedora" ]; then
        if command_exists dnf; then
            dnf install -y docker
        else
            yum install -y docker
        fi
        systemctl enable docker
        systemctl start docker
    elif [ "$OS" = "alpine" ]; then
        apk add --no-cache docker
        rc-update add docker boot
        service docker start
    else
        print_error "Unable to detect OS for Docker installation"
        exit 1
    fi

    # Verify Docker installation
    if ! command_exists docker; then
        print_error "Docker installation failed"
        exit 1
    fi

    print_info "Docker installed successfully"
}

# Function to generate random password
generate_password() {
    openssl rand -base64 16 | tr -d "=+/" | cut -c1-16
}

# Function to generate random prefix (8 ASCII characters)
generate_prefix() {
    cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 8 | head -n 1
}

# Function to generate random port (excluding 65535 and well-known ports < 1024)
generate_port() {
    while true; do
        # Generate port between 1024 and 65534
        port=$((RANDOM % 64511 + 1024))
        if [ "$port" -ne 65535 ] && [ "$port" -ge 1024 ]; then
            echo "$port"
            break
        fi
    done
}

# Function to check if port is in use
check_port() {
    local port=$1
    if command_exists ss; then
        ss -tuln 2>/dev/null | grep -q ":$port " && return 0 || return 1
    elif command_exists netstat; then
        netstat -tuln 2>/dev/null | grep -q ":$port " && return 0 || return 1
    else
        # If we can't check, try to bind to the port
        if command_exists timeout && command_exists nc; then
            timeout 1 nc -l -p "$port" >/dev/null 2>&1 && return 1 || return 0
        else
            # If we can't check, assume it's available
            return 1
        fi
    fi
}

# Function to get external IP
get_external_ip() {
    print_info "Detecting external IP address..."
    local ip
    
    # Try multiple services
    for service in "ifconfig.me" "ipinfo.io/ip" "icanhazip.com" "api.ipify.org"; do
        ip=$(curl -s --max-time 5 "https://$service" 2>/dev/null || curl -s --max-time 5 "http://$service" 2>/dev/null)
        if [ -n "$ip" ] && [[ "$ip" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
            print_info "External IP: $ip"
            echo "$ip"
            return 0
        fi
    done
    
    print_error "Failed to detect external IP address"
    exit 1
}

# Function to install Caddy
install_caddy() {
    if command_exists caddy; then
        print_info "Caddy is already installed"
        return
    fi

    print_info "Installing Caddy..."
    
    if [ "$OS" = "debian" ] || [ "$OS" = "ubuntu" ]; then
        apt-get update -qq
        apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
        curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
        curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
        apt-get update -qq
        apt-get install -y caddy
    elif [ "$OS" = "rhel" ] || [ "$OS" = "centos" ] || [ "$OS" = "fedora" ]; then
        if command_exists dnf; then
            dnf install -y 'dnf-command(copr)'
            dnf copr enable -y @caddy/caddy
            dnf install -y caddy
        else
            yum install -y yum-plugin-copr
            yum copr enable -y @caddy/caddy
            yum install -y caddy
        fi
    else
        # Fallback: install from official script
        print_info "Installing Caddy using official script..."
        curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/setup.rpm.sh' | bash
        if command_exists dnf; then
            dnf install -y caddy
        else
            yum install -y caddy
        fi
    fi

    # Verify Caddy installation
    if ! command_exists caddy; then
        print_error "Caddy installation failed"
        exit 1
    fi

    print_info "Caddy installed successfully"
}

# Function to get application version from container
get_app_version() {
    local container_name=$1
    local version="unknown"    
  
    # Try to get version via Python import
    if [ "$version" = "unknown" ]; then
        local python_version=$(docker exec "$container_name" python3 -c "import sys; sys.path.insert(0, '/app'); from version import VERSION; print(VERSION)" 2>/dev/null)
        if [ -n "$python_version" ]; then
            version="$python_version"
        fi
    fi
    
    echo "$version"
}

# Function to configure Caddy
configure_caddy() {
    local domain=$1
    local http_port=$2
    local web_prefix=$3
    
    print_info "Configuring Caddy for domain: $domain"
    
    # Create Caddyfile
    local caddyfile="/etc/caddy/Caddyfile"
    
    # Backup existing Caddyfile if it exists
    if [ -f "$caddyfile" ]; then
        print_warning "Backing up existing Caddyfile to ${caddyfile}.backup"
        cp "$caddyfile" "${caddyfile}.backup"
    fi
    
    # Create Caddyfile
    # Note: nip.io domains work with Let's Encrypt, but may take a moment to verify
    cat > "$caddyfile" <<EOF
$domain {
    # Reverse proxy to the application
    reverse_proxy localhost:$http_port {
        # Preserve the original request path
        header_up Host {host}
        header_up X-Real-IP {remote}
        header_up X-Forwarded-For {remote}
        header_up X-Forwarded-Proto {scheme}
    }
    
    # Security headers
    header {
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        X-XSS-Protection "1; mode=block"
    }
    
    # Logging
    log {
        output file /var/log/caddy/access.log
    }
}
EOF

    # Create log directory if it doesn't exist
    mkdir -p /var/log/caddy
    
    # Test Caddyfile configuration
    if caddy validate --config "$caddyfile" 2>/dev/null; then
        print_info "Caddyfile configuration is valid"
    else
        print_warning "Caddyfile validation failed, but continuing..."
    fi
    
    # Reload Caddy
    if command_exists systemctl; then
        if systemctl is-active --quiet caddy 2>/dev/null; then
            print_info "Reloading Caddy configuration..."
            systemctl reload caddy 2>/dev/null || systemctl restart caddy
        else
            print_info "Starting Caddy service..."
            systemctl enable caddy 2>/dev/null || true
            systemctl start caddy
        fi
    else
        # Fallback: try to start Caddy directly
        print_warning "systemctl not available, trying to start Caddy directly..."
        caddy run --config "$caddyfile" &
    fi
    
    # Wait a bit for Caddy to start and obtain certificate
    print_info "Waiting for Caddy to start and obtain SSL certificate (this may take up to 30 seconds)..."
    sleep 5
    
    # Check if Caddy is running
    local max_attempts=6
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if command_exists systemctl; then
            if systemctl is-active --quiet caddy 2>/dev/null; then
                print_info "Caddy is running"
                return 0
            fi
        else
            # Check if Caddy process is running
            if pgrep -x caddy >/dev/null 2>&1; then
                print_info "Caddy is running"
                return 0
            fi
        fi
        sleep 5
        attempt=$((attempt + 1))
    done
    
    if command_exists systemctl; then
        print_warning "Caddy service may not be running properly. Check logs with: journalctl -u caddy"
    else
        print_warning "Caddy may not be running properly. Check Caddy logs."
    fi
    return 1
}

# Main installation function
main() {
    print_info "WireGuard Obfuscator Easy - Installation Script"
    print_info "================================================"
    
    # Check if running as root
    if [ "$EUID" -ne 0 ]; then
        print_error "Please run this script as root"
        print_info "You can use: sudo bash $0"
        exit 1
    fi
    
    # Detect OS
    detect_os
    print_info "Detected OS: $OS"
    
    # Install curl if needed
    if ! command_exists curl; then
        install_curl
    fi
    
    # Install Docker
    install_docker
    
    # Verify Docker is running
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker is installed but not running. Please start Docker and try again."
        if command_exists systemctl; then
            print_info "Try: systemctl start docker"
        fi
        exit 1
    fi
    
    # Get external IP
    EXTERNAL_IP=$(get_external_ip)
    
    # Generate domain using nip.io
    DOMAIN="${EXTERNAL_IP}.nip.io"
    print_info "Using domain: $DOMAIN"
    
    # Generate random values
    print_info "Generating random configuration values..."
    ADMIN_PASSWORD=$(generate_password)
    WEB_PREFIX="/$(generate_prefix)/"
    HTTP_PORT=$(generate_port)
    
    # Ensure HTTP port is not in use
    local max_port_attempts=10
    local port_attempt=0
    while check_port "$HTTP_PORT"; do
        if [ $port_attempt -ge $max_port_attempts ]; then
            print_error "Failed to find available HTTP port after $max_port_attempts attempts"
            exit 1
        fi
        print_warning "Port $HTTP_PORT is already in use, generating new port..."
        HTTP_PORT=$(generate_port)
        port_attempt=$((port_attempt + 1))
    done
    
    WIREGUARD_PORT=$(generate_port)
    
    # Ensure WireGuard port is not in use
    port_attempt=0
    while check_port "$WIREGUARD_PORT"; do
        if [ $port_attempt -ge $max_port_attempts ]; then
            print_error "Failed to find available WireGuard port after $max_port_attempts attempts"
            exit 1
        fi
        print_warning "Port $WIREGUARD_PORT is already in use, generating new port..."
        WIREGUARD_PORT=$(generate_port)
        port_attempt=$((port_attempt + 1))
    done
    
    print_info "Generated configuration:"
    print_info "  HTTP Port: $HTTP_PORT"
    print_info "  WireGuard Port: $WIREGUARD_PORT"
    print_info "  Web Prefix: $WEB_PREFIX"
    print_info "  Admin Password: $ADMIN_PASSWORD"
    
    # Create config directory
    mkdir -p "$CONFIG_DIR"
    print_info "Config directory: $CONFIG_DIR"
    
    # Stop and remove existing container if it exists
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        print_warning "Stopping and removing existing container..."
        docker stop "$CONTAINER_NAME" 2>/dev/null || true
        docker rm "$CONTAINER_NAME" 2>/dev/null || true
    fi
    
    # Pull Docker image
    print_info "Pulling Docker image: $IMAGE_NAME"
    docker pull "$IMAGE_NAME" || {
        print_error "Failed to pull Docker image. Make sure the image exists and you have internet connection."
        exit 1
    }
    
    # Run Docker container
    print_info "Starting Docker container..."
    docker run -d \
        --name "$CONTAINER_NAME" \
        -v "$CONFIG_DIR:/config" \
        -v /etc/timezone:/etc/timezone:ro \
        -e WEB_PREFIX="$WEB_PREFIX" \
        -e EXTERNAL_IP="$EXTERNAL_IP" \
        -e EXTERNAL_PORT="$WIREGUARD_PORT" \
        -e ADMIN_PASSWORD="$ADMIN_PASSWORD" \
        -p "${WIREGUARD_PORT}:${WIREGUARD_PORT}/udp" \
        -p "${HTTP_PORT}:5000/tcp" \
        --cap-add NET_ADMIN \
        --cap-add SYS_MODULE \
        --sysctl net.ipv4.ip_forward=1 \
        --sysctl net.ipv4.conf.all.src_valid_mark=1 \
        --restart unless-stopped \
        "$IMAGE_NAME" || {
        print_error "Failed to start Docker container"
        exit 1
    }
    
    # Wait for container to be ready
    print_info "Waiting for container to be ready..."
    sleep 5
    
    # Check if container is running
    local max_wait=30
    local wait_time=0
    while [ $wait_time -lt $max_wait ]; do
        if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
            print_info "Container is running"
            break
        fi
        sleep 2
        wait_time=$((wait_time + 2))
    done
    
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        print_error "Container failed to start. Check logs with: docker logs $CONTAINER_NAME"
        exit 1
    fi
    
    # Wait a bit more for the application to be ready
    print_info "Waiting for application to be ready..."
    sleep 5
    
    # Check if application is responding
    if command_exists curl; then
        local max_health_checks=10
        local health_check=0
        while [ $health_check -lt $max_health_checks ]; do
            if curl -s -f -o /dev/null "http://localhost:$HTTP_PORT$WEB_PREFIX" 2>/dev/null || \
               curl -s -f -o /dev/null "http://127.0.0.1:$HTTP_PORT$WEB_PREFIX" 2>/dev/null; then
                print_info "Application is responding"
                break
            fi
            sleep 2
            health_check=$((health_check + 1))
        done
        if [ $health_check -eq $max_health_checks ]; then
            print_warning "Application may not be fully ready yet. It should be available shortly."
        fi
    fi
    
    # Get application version from container
    print_info "Getting application version..."
    APP_VERSION=$(get_app_version "$CONTAINER_NAME")
    if [ "$APP_VERSION" != "unknown" ]; then
        print_info "Application version: v$APP_VERSION"
    else
        print_warning "Could not determine application version"
        APP_VERSION=""
    fi
    
    # Install and configure Caddy
    print_info "Setting up HTTPS with Caddy..."
    install_caddy
    
    # Configure Caddy
    if configure_caddy "$DOMAIN" "$HTTP_PORT" "$WEB_PREFIX"; then
        HTTPS_ENABLED=true
        # Wait a bit more for SSL certificate to be obtained
        print_info "Waiting for SSL certificate to be obtained..."
        sleep 10
    else
        HTTPS_ENABLED=false
        print_warning "HTTPS setup failed. You can configure it manually later."
    fi
    
    # Print summary
    echo ""
    print_info "================================================"
    print_info "Installation completed successfully!"
    if [ -n "$APP_VERSION" ]; then
        print_info "Installed version: v$APP_VERSION"
    fi
    print_info "================================================"
    echo ""
    print_info "Access Information:"
    echo ""
    
    if [ "$HTTPS_ENABLED" = true ]; then
        print_info "HTTPS URL: https://$DOMAIN$WEB_PREFIX"
        print_warning "HTTP URL: http://$EXTERNAL_IP:$HTTP_PORT$WEB_PREFIX (not recommended)"
    else
        print_info "HTTP URL: http://$EXTERNAL_IP:$HTTP_PORT$WEB_PREFIX"
        print_warning "HTTPS is not configured. Please set up Caddy manually."
    fi
    
    echo ""
    print_info "Login Credentials:"
    print_info "  Username: admin"
    print_info "  Password: $ADMIN_PASSWORD"
    echo ""
    
    print_info "Configuration:"
    print_info "  Container name: $CONTAINER_NAME"
    print_info "  Config directory: $CONFIG_DIR"
    print_info "  WireGuard port: $WIREGUARD_PORT"
    print_info "  HTTP port: $HTTP_PORT"
    echo ""
    
    print_warning "IMPORTANT: Save these credentials in a secure location!"
    
    # Save configuration to file
    local config_file="$CONFIG_DIR/install_config.txt"
    cat > "$config_file" <<EOF
WireGuard Obfuscator Easy - Installation Configuration
=====================================================
Installation Date: $(date)
$(if [ -n "$APP_VERSION" ]; then echo "Installed Version: v$APP_VERSION"; fi)
Domain: $DOMAIN
External IP: $EXTERNAL_IP

Access URLs:
$(if [ "$HTTPS_ENABLED" = true ]; then echo "  HTTPS: https://$DOMAIN$WEB_PREFIX"; else echo "  HTTP: http://$EXTERNAL_IP:$HTTP_PORT$WEB_PREFIX"; fi)

Login Credentials:
  Username: admin
  Password: $ADMIN_PASSWORD

Configuration:
  Container name: $CONTAINER_NAME
  Config directory: $CONFIG_DIR
  WireGuard port: $WIREGUARD_PORT
  HTTP port: $HTTP_PORT
  Web prefix: $WEB_PREFIX
EOF
    chmod 600 "$config_file"
    print_info "Configuration saved to: $config_file"
    echo ""
    
    print_info "Useful commands:"
    print_info "  View container logs: docker logs $CONTAINER_NAME"
    print_info "  Stop container: docker stop $CONTAINER_NAME"
    print_info "  Start container: docker start $CONTAINER_NAME"
    print_info "  Restart container: docker restart $CONTAINER_NAME"
    echo ""
}

# Run main function
main "$@"

