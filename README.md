# WireGuard Obfuscator Easy

**WireGuard Obfuscator Easy** is a Docker container-based web management interface for WireGuard VPN servers with traffic obfuscation (via WireGuard Obfuscator) support. It provides an intuitive web UI and REST API for managing WireGuard clients, configuring obfuscation settings, and monitoring server statistics.

This project integrates with [WireGuard Obfuscator](https://github.com/ClusterM/wg-obfuscator) to help bypass ISP and government restrictions on WireGuard traffic.

> **Note:** This application is designed to run exclusively as a Docker container. It is not intended to run directly on the host system.

## Features

- 🌐 **Web-based Management Interface** - Modern, responsive UI built with React and TypeScript
- 🔐 **Client Management** - Create, edit, delete, and manage WireGuard clients with automatic client configuration generation
- 📊 **Real-time Statistics** - Monitor server status, client connections, and traffic statistics
- 🛡️ **Traffic Obfuscation** - Configure and manage WireGuard Obfuscator for bypassing DPI restrictions
- 🔒 **Secure Authentication** - JWT-based authentication with rate limiting protection
- 📱 **Multi-language Support** - English and Russian interfaces
- 🐳 **Docker-Only** - Designed exclusively for Docker containers
- 🚀 **Easy Installation** - One-command automated installation script
- 🔒 **HTTPS Support** - Automatic SSL certificate management with Caddy (via installation script)
- 📡 **REST API** - Full OpenAPI 3.0 specification for integration

## Quick Start

### Automated Installation

The easiest way to get started is using the automated installation script:
```bash
curl -Ls https://raw.githubusercontent.com/ClusterM/wg-obfuscator-easy/master/install.sh | bash
```

The installation script will:
1. Check for root privileges
2. Install Docker and required packages
3. Detect your server's external IP address
4. Generate a domain using nip.io
5. Generate random configuration values (admin password, web prefix, ports)
6. Pull and run the Docker container
7. Install and configure Caddy (outside the container) for HTTPS with automatic SSL certificates
8. Display access information and credentials

After installation, you'll receive:
- HTTPS URL (via nip.io domain) - if Caddy was installed
- HTTP URL (direct access to container) - always available
- Admin username and password
- Configuration file location

> **Note:** Caddy is installed outside the Docker container only when using the automated installation script. For manual Docker installations, you'll need to set up HTTPS separately or access the container directly via HTTP.

### Manual Docker Installation

If you prefer manual setup without the automated script:

```bash
docker run -d \
  --name wg-obf-easy \
  -v ~/.wg-obf-easy:/config \
  -v /etc/timezone:/etc/timezone:ro \
  -e WEB_PREFIX=/your-prefix/ \
  -e EXTERNAL_IP=your.server.ip \
  -e EXTERNAL_PORT=57159 \
  -e ADMIN_PASSWORD=your-secure-password \
  -p 57159:57159/udp \
  -p 5000:5000/tcp \
  --cap-add NET_ADMIN \
  --cap-add SYS_MODULE \
  --sysctl net.ipv4.ip_forward=1 \
  --sysctl net.ipv4.conf.all.src_valid_mark=1 \
  --restart unless-stopped \
  clustermeerkat/wg-obf-easy:latest
```

After starting the container, access the web interface at:
- HTTP: `http://your-server-ip:5000/your-prefix/`

For HTTPS, you'll need to set up a reverse proxy (like Nginx, Caddy, or Traefik) outside the container, or use the automated installation script which sets up Caddy automatically.

### Environment Variables

- `WEB_PREFIX` - Web interface path prefix (e.g., `/vpn/`)
- `EXTERNAL_IP` - Your server's external IP address
- `EXTERNAL_PORT` - WireGuard port (UDP)
- `ADMIN_PASSWORD` - Admin password (default: `admin`)
- `AUTH_ENABLED` - Enable/disable authentication (default: `true`)
- `SSL_CERT_FILE` - Path to SSL certificate file (optional, for HTTPS)
- `SSL_KEY_FILE` - Path to SSL private key file (optional, for HTTPS)

## Docker Images

Docker images are available on Docker Hub: **`clustermeerkat/wg-obf-easy`**

### Available Tags

- `latest` - Latest stable release
- `nightly` - Latest build from main branch (may be unstable)
- Version tags (e.g., `1.0`) - Specific version releases

### Supported Architectures

- `linux/amd64`
- `linux/arm64`
- `linux/arm/v7`
- `linux/arm/v6`
- `linux/arm/v5`
- `linux/ppc64le`
- `linux/s390x`

## Building from Source

### Prerequisites

- Node.js 18+ and npm
- Python 3.9+
- Docker and Docker Buildx (for multi-arch builds)

### Build Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ClusterM/wg-obfuscator-easy.git
   cd wg-obfuscator-easy
   ```

2. **Build frontend:**
   ```bash
   cd frontend
   npm install
   npm run build
   cd ..
   ```

3. **Build Docker image:**
   ```bash
   make build
   ```

   Or use the Makefile targets:
   - `make all` or `make build` - Build multi-arch image without pushing
   - `make push` - Build and push multi-arch image
   - `make release` - Build and push with version tag from `backend/version.py`
   - `make clean` - Clean build artifacts

### Custom Build Options

You can override Makefile variables:

```bash
make build PLATFORMS=linux/amd64,linux/arm64 TAG=nightly IMAGE_NAME=myregistry/wg-obf-easy
```

## Project Structure

```
wg-obf-easy/
├── backend/                 # Flask backend application
│   ├── app/                 # Main application package
│   │   ├── api/             # REST API endpoints
│   │   ├── auth/            # Authentication
│   │   ├── clients/         # Client management
│   │   ├── config/          # Configuration management
│   │   ├── obfuscator/      # Obfuscator integration
│   │   ├── wireguard/       # WireGuard management
│   │   └── ...
│   ├── version.py           # Application version
│   └── requirements.txt     # Python dependencies
├── frontend/                # React frontend application
│   ├── src/
│   │   ├── pages/           # Page components
│   │   ├── components/      # Reusable components
│   │   ├── i18n/           # Translations
│   │   └── ...
│   └── package.json
├── static/                  # Built frontend files (generated)
├── Dockerfile               # Docker image definition
├── install.sh              # Automated installation script
├── Makefile                # Build automation
├── api.yaml                # OpenAPI 3.0 specification
└── README.md               # This file
```

## Web Interface

The web interface provides:

- **Dashboard** - Server status, statistics, and system information
- **Clients** - Manage WireGuard clients (create, edit, delete, download configs)
- **Configuration** - Server and WireGuard settings
- **Real-time Updates** - Automatic refresh of statistics and status

### Accessing the Web Interface

**With automated installation script:**
- HTTPS: `https://your-domain.nip.io/your-prefix/` (via Caddy reverse proxy)
- HTTP: `http://your-server-ip:port/your-prefix/` (direct container access)

**With manual Docker installation:**
- HTTP: `http://your-server-ip:5000/your-prefix/` (direct container access)
- HTTPS: Set up your own reverse proxy (Nginx, Caddy, Traefik, etc.)

Default credentials:
- Username: `admin`
- Password: (generated during installation or set via `ADMIN_PASSWORD`)

## REST API

The application provides a complete REST API documented in OpenAPI 3.0 format. See `api.yaml` for full specification.

### API Endpoints

- **Authentication**: `/api/auth/login` - Login and get JWT token
- **Clients**: `/api/clients/*` - Client management (CRUD operations)
- **Configuration**: `/api/config/*` - Server configuration
- **Statistics**: `/api/stats/*` - Server and client statistics
- **Health**: `/health` - Health check endpoint

### Authentication

Most API endpoints require authentication. Include the JWT token in the `Authorization` header:

```
Authorization: Bearer <your-jwt-token>
```

### Rate Limiting

- Login endpoint: 5 attempts per minute per IP
- Default limits: 200 requests per hour, 50 per minute

## Configuration

### WireGuard Configuration

WireGuard settings are managed through the web interface or API. Key settings include:

- Subnet configuration
- WAN interface
- WireGuard interface name
- Obfuscation settings

### Obfuscator Configuration

The obfuscator integrates with [WireGuard Obfuscator](https://github.com/ClusterM/wg-obfuscator). Configuration is managed through the web interface.

Key features:
- Enable/disable obfuscation
- Configure masking types (NONE, STUN)
- Set obfuscator ports
- View real-time obfuscator logs

## Development

This application is designed to run in Docker containers. For development, you can build and run the container locally:

1. **Build the Docker image:**
   ```bash
   make build
   ```

2. **Run the container:**
   ```bash
   docker run -d \
     --name wg-obf-easy-dev \
     -v ~/.wg-obf-easy:/config \
     -v /etc/timezone:/etc/timezone:ro \
     -e WEB_PREFIX=/ \
     -e EXTERNAL_IP=$(curl -s ifconfig.me) \
     -e EXTERNAL_PORT=57159 \
     -e ADMIN_PASSWORD=admin \
     -p 57159:57159/udp \
     -p 5000:5000/tcp \
     --cap-add NET_ADMIN \
     --cap-add SYS_MODULE \
     --sysctl net.ipv4.ip_forward=1 \
     --sysctl net.ipv4.conf.all.src_valid_mark=1 \
     clustermeerkat/wg-obf-easy:nightly
   ```

3. **Access the development container:**
   - HTTP: `http://localhost:5000/`

### Frontend Development (Outside Container)

For frontend development, you can run the frontend separately:

1. **Install dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Run development server:**
   ```bash
   npm run dev
   ```

3. **Build for production:**
   ```bash
   npm run build
   ```

Note: The frontend needs to connect to a running backend container. Configure the API endpoint in your frontend configuration.

## Security Considerations

- **Change default password** - Always change the admin password after installation
- **Use HTTPS** - Enable HTTPS in production (automatic with installation script via Caddy)
- **Firewall** - Configure firewall rules to restrict access to the container ports
- **Rate limiting** - API endpoints are rate-limited to prevent abuse
- **Authentication** - JWT tokens expire after 24 hours
- **Container isolation** - The application runs in a Docker container with required Linux capabilities
- **Reverse proxy** - For production, use a reverse proxy (Caddy, Nginx, etc.) outside the container for additional security

## Troubleshooting

### Container won't start

- Check Docker logs: `docker logs wg-obf-easy`
- Verify required capabilities: `NET_ADMIN`, `SYS_MODULE`
- Check port availability and firewall rules

### Can't access web interface

- Verify the container is running: `docker ps`
- Check port mapping and firewall rules
- Verify `WEB_PREFIX` matches your URL path

### WireGuard not working

- Check WireGuard service status in Dashboard
- Verify external IP and port configuration
- Check obfuscator logs for errors

### SSL certificate issues

- Caddy is only installed by the automated installation script (outside the container)
- For nip.io domains, certificates are obtained automatically via Let's Encrypt
- Check Caddy logs: `journalctl -u caddy`
- Verify DNS resolution for your domain
- If using manual installation, set up your own reverse proxy with SSL certificates

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Related Projects

- [WireGuard Obfuscator](https://github.com/ClusterM/wg-obfuscator) - The underlying obfuscation tool
- [WireGuard](https://www.wireguard.com/) - Modern VPN protocol

## Support

For issues and questions:
- GitHub Issues: [Create an issue](https://github.com/ClusterM/wg-obfuscator-easy/issues)
- Email: cluster@cluster.wtf

## Donate

* [GitHub Sponsors](https://github.com/sponsors/ClusterM)
* [Buy Me A Coffee](https://www.buymeacoffee.com/cluster)
* [Sber](https://messenger.online.sberbank.ru/sl/Lnb2OLE4JsyiEhQgC)
* [Donation Alerts](https://www.donationalerts.com/r/clustermeerkat)
* [Boosty](https://boosty.to/cluster)
