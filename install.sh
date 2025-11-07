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
# 7. Ask user if they want HTTPS (interactive mode)
# 8. Configure Caddy for HTTPS with automatic SSL certificates (if enabled)
# 9. Display access information and credentials
#
# Usage:
#   wget https://raw.githubusercontent.com/ClusterM/wg-obfuscator-easy/master/install.sh -O install.sh && bash install.sh
#
# IMPORTANT: This script must be run interactively (not through a pipe).
#            It will guide you through all configuration steps.
#

set -e

# Trap to handle errors (only for critical failures)
trap 'print_error "Installation failed at line $LINENO. Please check the error messages above."' ERR INT TERM

# Colors for output
RED='\033[0;31m'T
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="docker.io/clustermeerkat/wg-obf-easy:latest"
CONTAINER_NAME="wg-obf-easy"
# Use root's home directory for config (since we run as root)
CONFIG_DIR="/root/.wg-obf-easy"
CONFIG_FILE="$CONFIG_DIR/install_config.json"
FIREWALL_BACKEND="none"
FIREWALL_BACKEND_STATE="unknown"
FIREWALL_RELOAD_REQUIRED=false
declare -a FIREWALL_PORTS_OPENED=()
declare -a FIREWALL_PORTS_SKIPPED=()
IPTABLES_PERSISTENCE_CONFIGURED=false

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} ${WHITE}$1${NC}"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} ${WHITE}$1${NC}"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} ${WHITE}$1${NC}"
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

install_systemd() {
    print_info "Installing systemd..."
    if [ "$OS" = "debian" ] || [ "$OS" = "ubuntu" ]; then
        apt-get update -qq
        apt-get install -y systemd
    elif [ "$OS" = "rhel" ] || [ "$OS" = "centos" ] || [ "$OS" = "fedora" ]; then
        dnf install -y systemd
    elif [ "$OS" = "alpine" ]; then
        apk add --no-cache systemd
    else
        print_error "Unable to detect OS for systemd installation"
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
        local docker_packages="docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin"
        if command_exists dnf; then
            if rpm -q podman-docker >/dev/null 2>&1; then
                print_warning "Removing podman-docker to avoid conflicts with Docker CE..."
                dnf remove -y podman-docker >/dev/null
            fi
            dnf install -y dnf-plugins-core
            if ! dnf repolist 2>/dev/null | grep -q "^docker-ce-stable"; then
                print_info "Adding official Docker CE repository..."
                dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo >/dev/null
            fi
            dnf install -y $docker_packages
        else
            if rpm -q podman-docker >/dev/null 2>&1; then
                print_warning "Removing podman-docker to avoid conflicts with Docker CE..."
                yum remove -y podman-docker >/dev/null
            fi
            yum install -y yum-utils
            if ! yum repolist 2>/dev/null | grep -q "^docker-ce-stable"; then
                print_info "Adding official Docker CE repository..."
                yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo >/dev/null
            fi
            yum install -y $docker_packages
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

detect_firewall_backend() {
    FIREWALL_BACKEND="none"
    FIREWALL_BACKEND_STATE="unknown"

    if command_exists firewall-cmd; then
        FIREWALL_BACKEND="firewalld"
        if firewall-cmd --state >/dev/null 2>&1; then
            FIREWALL_BACKEND_STATE="active"
        else
            FIREWALL_BACKEND_STATE="inactive"
        fi
        return
    fi

    if command_exists ufw; then
        FIREWALL_BACKEND="ufw"
        if ufw status 2>/dev/null | head -n1 | grep -qi "active"; then
            FIREWALL_BACKEND_STATE="active"
        else
            FIREWALL_BACKEND_STATE="inactive"
        fi
        return
    fi

    if command_exists iptables; then
        FIREWALL_BACKEND="iptables"
        FIREWALL_BACKEND_STATE="active"
        return
    fi
}

record_firewall_result() {
    local spec=$1
    local outcome=$2
    local -n target_array=$3

    for existing in "${target_array[@]}"; do
        if [ "$existing" = "$spec" ]; then
            return
        fi
    done

    target_array+=("$spec")
    if [ "$outcome" = "opened" ]; then
        print_info "Firewall: port $spec opened"
    fi
}

ensure_iptables_persistence() {
    if [ "$FIREWALL_BACKEND" != "iptables" ]; then
        return
    fi

    local install_performed=false

    if [ "$IPTABLES_PERSISTENCE_CONFIGURED" != "true" ]; then
        case "$OS" in
            debian|ubuntu)
                print_info "Configuring iptables persistence using netfilter-persistent..."
                export DEBIAN_FRONTEND=noninteractive
                apt-get update -qq
                apt-get install -y netfilter-persistent iptables-persistent
                install_performed=true
                ;;
            rhel|centos|fedora)
                print_info "Configuring iptables persistence using iptables-services..."
                if command_exists dnf; then
                    dnf install -y iptables-services
                else
                    yum install -y iptables-services
                fi
                systemctl enable iptables >/dev/null 2>&1 || true
                systemctl start iptables >/dev/null 2>&1 || true
                install_performed=true
                ;;
            alpine)
                print_info "Configuring iptables persistence using iptables-openrc..."
                apk add --no-cache iptables ip6tables iptables-openrc
                rc-update add iptables default >/dev/null 2>&1 || true
                rc-update add ip6tables default >/dev/null 2>&1 || true
                install_performed=true
                ;;
            *)
                print_warning "Automatic iptables persistence is not supported for OS: $OS. Please configure rule saving manually."
                IPTABLES_PERSISTENCE_CONFIGURED=true
                return
                ;;
        esac
        IPTABLES_PERSISTENCE_CONFIGURED=true
    fi

    local save_success=false

    case "$OS" in
        debian|ubuntu)
            if command_exists netfilter-persistent; then
                netfilter-persistent save >/dev/null 2>&1 && save_success=true
            fi
            if [ "$save_success" = false ]; then
                mkdir -p /etc/iptables
                if iptables-save > /etc/iptables/rules.v4 2>/dev/null; then
                    save_success=true
                fi
                if command_exists ip6tables-save; then
                    ip6tables-save > /etc/iptables/rules.v6 2>/dev/null || true
                fi
            fi
            ;;
        rhel|centos|fedora)
            mkdir -p /etc/sysconfig
            if iptables-save > /etc/sysconfig/iptables 2>/dev/null; then
                save_success=true
            fi
            if command_exists ip6tables-save; then
                ip6tables-save > /etc/sysconfig/ip6tables 2>/dev/null || true
            fi
            ;;
        alpine)
            if command_exists rc-service; then
                rc-service iptables save >/dev/null 2>&1 && save_success=true
                rc-service ip6tables save >/dev/null 2>&1 || true
            fi
            if [ "$save_success" = false ]; then
                mkdir -p /etc/iptables
                if iptables-save > /etc/iptables/rules-save 2>/dev/null; then
                    save_success=true
                fi
                if command_exists ip6tables-save; then
                    ip6tables-save > /etc/iptables/rules6-save 2>/dev/null || true
                fi
            fi
            ;;
        *)
            return
            ;;
    esac

    if [ "$save_success" = true ]; then
        if [ "$install_performed" = true ]; then
            print_info "iptables persistence configured and current rules saved."
        else
            print_info "iptables rules saved for persistence."
        fi
    else
        print_warning "Failed to confirm iptables rule persistence. Please verify manually."
    fi
}

open_firewall_port() {
    local port=$1
    local protocol=${2:-tcp}
    local spec="${port}/${protocol}"

    case "$FIREWALL_BACKEND" in
        firewalld)
            if [ "$FIREWALL_BACKEND_STATE" != "active" ]; then
                print_warning "firewalld detected but not running. Skipping automatic opening of $spec."
                record_firewall_result "$spec" "skipped" FIREWALL_PORTS_SKIPPED
                return
            fi

            local runtime_added=false
            local permanent_added=false

            if ! firewall-cmd --query-port="$spec" >/dev/null 2>&1; then
                if firewall-cmd --add-port="$spec" >/dev/null 2>&1; then
                    runtime_added=true
                else
                    print_warning "Failed to open $spec in firewalld runtime configuration."
                fi
            fi

            if ! firewall-cmd --permanent --query-port="$spec" >/dev/null 2>&1; then
                if firewall-cmd --permanent --add-port="$spec" >/dev/null 2>&1; then
                    permanent_added=true
                    FIREWALL_RELOAD_REQUIRED=true
                else
                    print_warning "Failed to add $spec to firewalld permanent configuration."
                fi
            fi

            if [ "$runtime_added" = true ] || [ "$permanent_added" = true ]; then
                record_firewall_result "$spec" "opened" FIREWALL_PORTS_OPENED
            else
                print_info "Firewall: port $spec already open in firewalld"
            fi
            ;;
        ufw)
            local status_line
            status_line=$(ufw status 2>/dev/null | head -n1 || echo "")
            if echo "$status_line" | grep -qi "inactive"; then
                print_warning "UFW detected but inactive. Port $spec was not modified."
                record_firewall_result "$spec" "skipped" FIREWALL_PORTS_SKIPPED
                return
            fi

            if ufw status numbered 2>/dev/null | grep -qw "$spec"; then
                print_info "Firewall: port $spec already allowed in UFW"
                return
            fi

            if ufw allow "$spec" >/dev/null 2>&1; then
                record_firewall_result "$spec" "opened" FIREWALL_PORTS_OPENED
            else
                print_warning "Failed to allow $spec via UFW."
                record_firewall_result "$spec" "skipped" FIREWALL_PORTS_SKIPPED
            fi
            ;;
        iptables)
            if ! command_exists iptables; then
                record_firewall_result "$spec" "skipped" FIREWALL_PORTS_SKIPPED
                print_warning "iptables command not available to open $spec."
                return
            fi

            if ! iptables -C INPUT -p "$protocol" --dport "$port" -j ACCEPT >/dev/null 2>&1; then
                if iptables -I INPUT -p "$protocol" --dport "$port" -j ACCEPT >/dev/null 2>&1; then
                    record_firewall_result "$spec" "opened" FIREWALL_PORTS_OPENED
                else
                    print_warning "Failed to add iptables rule for $spec."
                    record_firewall_result "$spec" "skipped" FIREWALL_PORTS_SKIPPED
                fi
            else
                print_info "Firewall: port $spec already allowed in iptables"
            fi

            if [ "$protocol" != "udp" ] && [ "$protocol" != "tcp" ]; then
                return
            fi

            if command_exists ip6tables; then
                if ! ip6tables -C INPUT -p "$protocol" --dport "$port" -j ACCEPT >/dev/null 2>&1; then
                    ip6tables -I INPUT -p "$protocol" --dport "$port" -j ACCEPT >/dev/null 2>&1 || true
                fi
            fi

            ensure_iptables_persistence
            ;;
        *)
            record_firewall_result "$spec" "skipped" FIREWALL_PORTS_SKIPPED
            print_warning "No supported firewall backend detected. Please ensure port $spec is reachable."
            ;;
    esac
}

finalize_firewall_changes() {
    if [ "$FIREWALL_BACKEND" = "firewalld" ] && [ "$FIREWALL_BACKEND_STATE" = "active" ] && [ "$FIREWALL_RELOAD_REQUIRED" = true ]; then
        if firewall-cmd --reload >/dev/null 2>&1; then
            print_info "firewalld reloaded to apply permanent firewall changes."
            FIREWALL_RELOAD_REQUIRED=false
        else
            print_warning "Failed to reload firewalld. Please reload it manually to apply changes."
        fi
    fi
}

# Function to get external IP
get_external_ip() {
    local ip
    
    # Try multiple services
    for service in "ifconfig.me" "ipinfo.io/ip" "icanhazip.com" "api.ipify.org"; do
        ip=$(curl -s --max-time 5 "https://$service" 2>/dev/null || curl -s --max-time 5 "http://$service" 2>/dev/null)
        if [ -n "$ip" ] && [[ "$ip" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
            echo "$ip"
            return 0
        fi
    done
    
    return 1
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
    local domain_or_host=$1
    local http_port=$2
    local web_prefix=${3:-/}
    local mode=${4:-https}
    local caddyfile="/etc/caddy/Caddyfile"
    local site_label
    local acme_email="${ACME_EMAIL}"

    if [ "$mode" = "https" ]; then
        if [ -z "$domain_or_host" ]; then
            print_error "Domain is required for HTTPS configuration"
            return 1
        fi
        site_label="$domain_or_host"
    else
        if [ -z "$domain_or_host" ]; then
            site_label=":80"
        else
            site_label="$domain_or_host"
            if [[ "$site_label" != http://* && "$site_label" != https://* && "$site_label" != :* ]]; then
                site_label="http://${site_label}"
            fi
        fi
        print_info "Configuring Caddy HTTP reverse proxy for host: $site_label"
    fi

    print_info "Configuring Caddy for target port: $http_port (proxying to $web_prefix)"

    # Backup existing Caddyfile if it exists
    if [ -f "$caddyfile" ]; then
        print_info "Backing up existing Caddyfile to ${caddyfile}.backup"
        cp "$caddyfile" "${caddyfile}.backup"
    fi

    if [ "$mode" = "https" ]; then
        print_info "Configuring Caddy domain with Let's Encrypt SSL certificate..."
        if [ -n "$acme_email" ] && echo "$acme_email" | grep -qE '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'; then
            cat > "$caddyfile" <<EOF
{
    email $acme_email
}

$site_label {
    reverse_proxy 127.0.0.1:$http_port {
        header_up Host {host}
        header_up X-Real-IP {remote}
        header_up X-Forwarded-For {remote}
        header_up X-Forwarded-Proto {scheme}
    }

    header {
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        X-XSS-Protection "1; mode=block"
    }

    log {
        output file /var/log/caddy/access.log
    }
}
EOF
        else
            cat > "$caddyfile" <<EOF
$site_label {
    reverse_proxy 127.0.0.1:$http_port {
        header_up Host {host}
        header_up X-Real-IP {remote}
        header_up X-Forwarded-For {remote}
        header_up X-Forwarded-Proto {scheme}
    }

    header {
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        X-XSS-Protection "1; mode=block"
    }

    log {
        output file /var/log/caddy/access.log
    }
}
EOF
        fi
    else
        cat > "$caddyfile" <<EOF
$site_label {
    reverse_proxy 127.0.0.1:$http_port {
        header_up Host {host}
        header_up X-Real-IP {remote}
        header_up X-Forwarded-For {remote}
        header_up X-Forwarded-Proto {scheme}
    }

    header {
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        X-XSS-Protection "1; mode=block"
    }

    log {
        output file /var/log/caddy/access.log
    }
}
EOF
    fi

    # Create log directory with proper permissions
    mkdir -p /var/log/caddy
    if command_exists chown; then
        # Try to set ownership to caddy user if it exists
        if id caddy >/dev/null 2>&1; then
            # Remove any existing log files that might have wrong ownership
            rm -f /var/log/caddy/access.log 2>/dev/null || true
            # Fix ownership of directory
            chown -R caddy:caddy /var/log/caddy 2>/dev/null || true
            # Create log file with correct ownership
            touch /var/log/caddy/access.log
            chown caddy:caddy /var/log/caddy/access.log 2>/dev/null || true
            chmod 644 /var/log/caddy/access.log 2>/dev/null || true
        fi
        chmod 755 /var/log/caddy
    fi
    
    # Test Caddyfile configuration
    if caddy validate --config "$caddyfile" 1>/dev/null 2>/dev/null; then
        print_info "Caddyfile configuration is valid"
    else
        print_warning "Caddyfile validation failed, but continuing..."
    fi
    
    # Reload or restart Caddy
    if command_exists systemctl; then
        if systemctl is-active --quiet caddy 2>/dev/null; then
            print_info "Reloading Caddy configuration..."
            # Use timeout to prevent hanging on reload
            # If reload fails or hangs, fall back to restart
            if timeout 10 systemctl reload caddy 2>/dev/null; then
                print_info "Caddy configuration reloaded"
            else
                print_warning "Caddy reload failed or timed out, restarting..."
                systemctl restart caddy
            fi
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
    
    # Wait a bit for Caddy to start and, if needed, obtain certificate
    if [ "$mode" = "https" ]; then
        print_info "Waiting for Caddy to start and obtain SSL certificate (this may take up to 30 seconds)..."
    else
        print_info "Waiting for Caddy to start (this may take up to 30 seconds)..."
    fi
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
    # Check if we can read from stdin (interactive mode required)
    if ! [ -t 0 ]; then
        print_error "================================================"
        print_error "This script requires interactive mode!"
        print_error "================================================"
        echo ""
        print_error "You cannot run this script through a pipe (curl ... | bash)."
        echo ""
        print_info "Please download and run it directly:"
        echo ""
        print_info "  curl -Ls https://raw.githubusercontent.com/ClusterM/wg-obfuscator-easy/master/install.sh -o install.sh"
        print_info "  bash install.sh"
        echo ""
        print_info "Or use wget:"
        print_info "  wget https://raw.githubusercontent.com/ClusterM/wg-obfuscator-easy/master/install.sh"
        print_info "  bash install.sh"
        echo ""
        exit 1
    fi
    
    print_info "================================================"
    print_info "WireGuard Obfuscator Easy - Installation Script"
    print_info "================================================"
    echo ""
    print_info "This script will guide you through the installation process."
    print_info "You will be asked a few questions to configure your setup."
    echo ""
    
    # Check if running as root
    if [ "$EUID" -ne 0 ]; then
        if command_exists sudo; then
            print_warning "This script must be run as root. Re-launching with sudo. You may be prompted for your password."
            exec sudo bash "$0" "$@"
        else
            print_error "This script must be run as root"
            echo ""
            print_info "Please run as root (for example, with sudo if available):"
            print_info "  sudo bash install.sh"
            echo ""
            exit 1
        fi
    fi
    
    # Detect OS
    detect_os
    print_info "Detected OS: $OS"

    detect_firewall_backend
    if [ "$FIREWALL_BACKEND" != "none" ]; then
        if [ "$FIREWALL_BACKEND_STATE" = "active" ]; then
            print_info "Detected firewall manager: $FIREWALL_BACKEND"
        else
            print_warning "Firewall manager detected ($FIREWALL_BACKEND) but appears inactive."
        fi
    else
        print_info "No supported firewall manager detected."
    fi

    print_info "Installing required packages... (this may take a while)"

    if ! command_exists systemctl; then
        # Install systemd if needed
        install_systemd
        if ! command_exists systemctl; then
            print_error "systemctl is not installed. Please install it and try again."
            exit 1
        fi
    fi
    
    if ! command_exists curl; then
        # Install curl if needed
        install_curl
    fi

    # Install Docker
    install_docker

    # Install Caddy
    install_caddy
    
    # Verify Docker is running
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker is installed but not running. Please start Docker and try again."
        if command_exists systemctl; then
            print_info "Try: systemctl start docker"
        fi
        exit 1
    fi
    
    # Get external IP
    print_info "Detecting external IP address..."
    EXTERNAL_IP=$(get_external_ip)
    if [ -z "$EXTERNAL_IP" ]; then
        print_error "Failed to detect external IP address"
        exit 1
    fi
    print_info "External IP: $EXTERNAL_IP"

    # Stop existing container if it exists to free the ports
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        docker stop "$CONTAINER_NAME" 1>/dev/null || true
    fi

    if command_exists systemctl; then
        # Stop Caddy if it is running to free the port
        if systemctl is-active --quiet caddy 2>/dev/null; then
            systemctl stop caddy
        fi
    fi

    CONFIG_EXISTS=false
    if [ -f "$CONFIG_FILE" ]; then
        CONFIG_EXISTS=true
        source "$CONFIG_FILE"
        ADMIN_PASSWORD=""
    else
        # Generate random values
        ADMIN_PASSWORD=$(generate_password)
        WIREGUARD_PORT=$(generate_port)
        WEB_PREFIX="/$(generate_prefix)/"
    fi
    HTTP_PORT=$(generate_port)
    # Ensure HTTP port is not in use
    local max_port_attempts=10
    local port_attempt=0
    while check_port "$HTTP_PORT"; do
        if [ $port_attempt -ge $max_port_attempts ]; then
            print_error "Failed to find available HTTP port after $max_port_attempts attempts"
            exit 1
        fi
        HTTP_PORT=$(generate_port)
        port_attempt=$((port_attempt + 1))
    done
    # Ensure WireGuard port is not in use
    port_attempt=0
    while check_port "$WIREGUARD_PORT"; do
        if [ $port_attempt -ge $max_port_attempts ]; then
            print_error "Failed to find available WireGuard port after $max_port_attempts attempts"
            exit 1
        fi
        WIREGUARD_PORT=$(generate_port)
        port_attempt=$((port_attempt + 1))
    done
    
    # Create config directory
    mkdir -p "$CONFIG_DIR"
    print_info "Config directory: $CONFIG_DIR"

    # Remove existing container if it exists to free the ports
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        docker rm "$CONTAINER_NAME" 1>/dev/null || true
    fi

    # Pull Docker image
    print_info "Pulling Docker image: $IMAGE_NAME..."
    docker pull "$IMAGE_NAME" 1>/dev/null || {
        print_error "Failed to pull Docker image. Make sure the image exists and you have internet connection."
        exit 1
    }

    # Run Docker container
    print_info "Starting WireGuard Obfuscator Easy Docker container..."
    docker run -d \
        --name "$CONTAINER_NAME" \
        -v "$CONFIG_DIR:/config" \
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
        "$IMAGE_NAME" 1>/dev/null || {
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
    
    # Get application version from container
    print_info "Getting application version..."
    APP_VERSION=$(get_app_version "$CONTAINER_NAME")
    if [ "$APP_VERSION" != "unknown" ]; then
        print_info "Application version: v$APP_VERSION"
    else
        print_warning "Could not determine application version"
        APP_VERSION=""
    fi    

    while true; do
        read -p "Do you want to enable HTTPS (recommended)? It requires a domain name, but you can use a free domain name. (y/N): " -r
        if [[ "$REPLY" =~ ^[Yy]$ ]]; then
            ENABLE_HTTPS=true
            break
        elif [[ -z "$REPLY" ]] || [[ "$REPLY" =~ ^[Nn]$ ]]; then
            ENABLE_HTTPS=false
            break
        fi
    done

    if [ "$ENABLE_HTTPS" = true ]; then
        # TODO: check reverse DNS for the domain, which should point to the server IP address
        while true; do
            read -p "Do you need a guide how to obtain a free domain name from DuckDNS? (Y/n/q): " -r
            if [[ "$REPLY" =~ ^[Qq]$ ]]; then
                ENABLE_HTTPS=false
                break
            elif [[ -z "$REPLY" ]] || [[ "$REPLY" =~ ^[Yy]$ ]]; then
                echo ""
                print_info "We'll use DuckDNS to create a free domain name for your server."
                print_info "Your server IP address is: $EXTERNAL_IP"
                echo ""
                print_info "Follow these steps to set up DuckDNS:"
                echo ""
                print_info "1. Open your web browser and go to: https://www.duckdns.org/"
                echo ""
                print_info "2. Click on 'Sign in with Google' or 'Sign in with GitHub'"
                print_info "   (You can use any Google or GitHub account - it's free)"
                echo ""
                print_info "3. After signing in, you'll see a page where you must:"
                print_info "   - Enter a new subdomain name (e.g., any name you want, but it must be unique and not already taken)"
                print_info "   - Enter your server IP address: $EXTERNAL_IP"
                print_info "   - Click 'add domain' or 'update ip'"
                echo ""
                # Get DuckDNS subdomain
                while true; do
                    print_info "After creating your DuckDNS domain, enter your DuckDNS subdomain name (or enter 'q' to cancel and continue without HTTPS)."
                    print_info "Example: If your domain is 'myvpn.duckdns.org', enter 'myvpn'."
                    echo ""
                    read -p "DuckDNS subdomain: " -r
                    if [[ "$REPLY" =~ ^[Qq]$ ]]; then
                        ENABLE_HTTPS=false
                        break
                    fi
                    local duckdns_subdomain="$REPLY"
                    if [ -z "$duckdns_subdomain" ]; then
                        print_error "Subdomain cannot be empty. Please enter your DuckDNS subdomain."
                        echo ""
                        continue
                    fi
                    # Basic validation - only alphanumeric and hyphens
                    if ! echo "$duckdns_subdomain" | grep -qE '^[a-zA-Z0-9-]+$'; then
                        print_error "Invalid subdomain. Use only letters, numbers, and hyphens."
                        echo ""
                        continue
                    fi
                    DOMAIN="${duckdns_subdomain}.duckdns.org"
                    break
                done
                break
            elif [[ "$REPLY" =~ ^[Nn]$ ]]; then
                while true; do
                    read -p "Enter your domain name (or enter 'q' to cancel and continue without HTTPS): " -r
                    if [[ "$REPLY" =~ ^[Qq]$ ]]; then
                        ENABLE_HTTPS=false
                        break
                    fi
                    DOMAIN="$REPLY"
                    if [ -z "$DOMAIN" ]; then
                        print_error "Domain cannot be empty. Please enter your domain name."
                        echo ""
                        continue
                    fi
                    if ! echo "$DOMAIN" | grep -qE '^[a-zA-Z0-9\.-]+\.[a-zA-Z]{2,}$'; then
                        print_error "Invalid domain name."
                        echo ""
                        continue
                    fi
                    break
                done
                break
            fi
        done
    fi

    DNS_RESOLVED=false
    if [ "$ENABLE_HTTPS" = true ]; then
        echo ""
        print_info "Checking if domain $DOMAIN points to your IP address ($EXTERNAL_IP)..."
        
        # Wait a bit for DNS to propagate
        sleep 5
        
        # Check DNS resolution
        local max_dns_checks=12
        local dns_check=0
        
        while [ $dns_check -lt $max_dns_checks ]; do
            local resolved_ip=$(getent hosts "$DOMAIN" 2>/dev/null | awk '{print $1}' | head -1)
            if [ -z "$resolved_ip" ]; then
                # Try with nslookup or host command if available
                if command_exists nslookup; then
                    resolved_ip=$(nslookup "$DOMAIN" 2>/dev/null | grep -A1 "Name:" | grep "Address:" | awk '{print $2}' | head -1)
                elif command_exists host; then
                    resolved_ip=$(host "$DOMAIN" 2>/dev/null | grep "has address" | awk '{print $4}' | head -1)
                fi
            fi
            
            if [ "$resolved_ip" = "$EXTERNAL_IP" ]; then
                DNS_RESOLVED=true
                print_info "DNS is correctly configured! Domain $DOMAIN points to $EXTERNAL_IP."
                break
            fi
            
            print_info "Waiting for DNS to propagate... (attempt $((dns_check + 1))/$max_dns_checks)"
            sleep 10
            dns_check=$((dns_check + 1))
        done
        
        if [ "$DNS_RESOLVED" = false ]; then
            print_warning "Could not verify DNS configuration automatically. Please check your DNS settings."
            print_warning "If you are using DuckDNS, please make sure you have added your domain and your server IP address."
            print_warning "It's possible that your DNS is not propagated yet. Please wait some time and try again. Some DNS providers take up to 24 hours to propagate."
            echo ""
            print_info "Let's continue without HTTPS for now."
            ENABLE_HTTPS=false
        else
            # Ask for email (optional for Let's Encrypt notifications)
            echo ""
            print_info "SSL Certificate Setup"
            print_info "Let's Encrypt will automatically provide SSL certificates for your domain."
            echo ""
            print_info "You can optionally provide an email address to receive notifications"
            print_info "when your certificate is about to expire (certificates are renewed automatically)."
            echo ""
            print_info "This email is completely optional - SSL certificates will work without it."
            echo ""
            while true; do
                read -p "Enter email address for notifications (or press Enter to skip): " -r
                if [ -z "$REPLY" ]; then
                    # Empty email - that's fine
                    ACME_EMAIL=""
                    print_info "Continuing without email. SSL certificates will still work perfectly."
                    break
                elif echo "$REPLY" | grep -qE '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'; then
                    # Valid email
                    ACME_EMAIL="$REPLY"
                    print_info "Email set: $ACME_EMAIL"
                    print_info "You'll receive notifications about certificate expiration (if any)."
                    break
                else
                    echo ""
                    print_error "Invalid email format!"
                    print_error "Please enter a valid email address (e.g., user@example.com)"
                    print_error "or press Enter without typing anything to skip."
                    echo ""
                fi
            done
            echo ""
        fi
    fi

    # Open firewall ports
    open_firewall_port "$WIREGUARD_PORT" "udp"
    open_firewall_port "80" "tcp"
    open_firewall_port "443" "tcp"

    # Install and configure Caddy if HTTPS is enabled
    HTTP_PORT_REAL=$HTTP_PORT
    if [ "$ENABLE_HTTPS" = true ]; then
        print_info "Setting up HTTPS with Caddy..."
        
        # Configure Caddy
        if ! configure_caddy "$DOMAIN" "$HTTP_PORT" "$WEB_PREFIX" "https"; then
            print_warning "HTTPS setup failed. Let's continue without HTTPS."
            systemctl stop caddy
            systemctl disable caddy
            ENABLE_HTTPS=false
        fi
    fi
    if [ "$ENABLE_HTTPS" = false ]; then
        # check if the 80 port is in use
        if ! check_port "80"; then
            print_info "Setting up HTTP reverse proxy with Caddy on port 80..."
            local http_proxy_host
            http_proxy_host="$DOMAIN"
            if [ -z "$http_proxy_host" ]; then
                http_proxy_host=":80"
            fi
            if ! configure_caddy "$http_proxy_host" "$HTTP_PORT" "$WEB_PREFIX" "http"; then
                print_warning "Failed to configure HTTP reverse proxy with Caddy. HTTP will remain available on port $HTTP_PORT."
                open_firewall_port "$HTTP_PORT" "tcp"
                systemctl stop caddy
                systemctl disable caddy
            else
                print_info "Caddy HTTP reverse proxy configured successfully."
                HTTP_PORT=80
            fi
        fi
    fi

    finalize_firewall_changes

    # Print summary
    echo ""
    print_info "================================================"
    print_info "Installation completed successfully!"
    if [ -n "$APP_VERSION" ]; then
        print_info "Installed version: v$APP_VERSION"
    fi
    print_info "================================================"
    echo ""


    if [ "$FIREWALL_BACKEND" != "none" ]; then
        local opened_ports=""
        local skipped_ports=""
        if [ ${#FIREWALL_PORTS_OPENED[@]} -gt 0 ]; then
            opened_ports=$(printf "%s\n" "${FIREWALL_PORTS_OPENED[@]}" | sort -u | tr '\n' ' ' | sed 's/ $//')
        fi
        if [ ${#FIREWALL_PORTS_SKIPPED[@]} -gt 0 ]; then
            skipped_ports=$(printf "%s\n" "${FIREWALL_PORTS_SKIPPED[@]}" | sort -u | tr '\n' ' ' | sed 's/ $//')
        fi

        if [ -n "$opened_ports" ]; then
            print_info "Firewall ($FIREWALL_BACKEND) opened ports: $opened_ports"
        fi
        if [ -n "$skipped_ports" ]; then
            print_warning "Firewall ports requiring manual configuration: $skipped_ports"
        fi

        if [ "$FIREWALL_BACKEND" = "ufw" ] && [ "$FIREWALL_BACKEND_STATE" != "active" ]; then
            print_warning "UFW rules were not applied automatically because UFW is inactive."
        fi
        if [ "$FIREWALL_BACKEND" = "firewalld" ] && [ "$FIREWALL_BACKEND_STATE" != "active" ]; then
            print_warning "firewalld rules were not applied automatically because the service is not running."
        fi
    fi
    echo ""

    print_info "Configuration:"
    print_info "  Container name: $CONTAINER_NAME"
    print_info "  WireGuard port: $WIREGUARD_PORT"
    print_info "  Web prefix: $WEB_PREFIX"
    if [ "$ENABLE_HTTPS" = true ]; then
        print_info "  HTTPS enabled: true"
    else
        print_info "  HTTPS enabled: false"
    fi
    echo ""

    if [ "$ENABLE_HTTPS" = true ]; then
        print_info "HTTP URL: http://$DOMAIN$WEB_PREFIX (not recommended - use HTTPS)"
        print_info "HTTPS URL: https://$DOMAIN$WEB_PREFIX (using Let's Encrypt certificate)"
    else
        if [ "$HTTP_PORT" = 80 ]; then
            print_info "HTTP URL: http://$EXTERNAL_IP$WEB_PREFIX"
        else
            print_info "HTTP URL: http://$EXTERNAL_IP:$HTTP_PORT$WEB_PREFIX"
        fi
    fi
    echo ""

    if [ "$CONFIG_EXISTS" = false ]; then
        print_info "Login Credentials:"
        print_info "  Username: admin"
        print_info "  Password: $ADMIN_PASSWORD"
    else
        print_info "Login Credentials are the same as the ones you used to install the script."
    fi
    echo ""
    
    if [ "$ENABLE_HTTPS" = true ]; then
        print_warning "It can some time for the certificate to be obtained. If HTTPS is not working, please wait a few minutes and try again."
    fi
    print_warning "Save these credentials in a secure location!"
    if [ "$ENABLE_HTTPS" = false ]; then
        print_warning "HTTPS is not enabled. You can enable it later by running the script again."
    fi
    
    # Save configuration to file
    cat > "$CONFIG_FILE" <<EOF
HTTP_PORT="$HTTP_PORT_REAL"
WEB_PREFIX="$WEB_PREFIX"
WIREGUARD_PORT="$WIREGUARD_PORT"
EOF
}

# Run main function
main "$@"

