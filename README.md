# WireGuard Obfuscator Easy

**WireGuard Obfuscator Easy** is a Docker container-based web management interface for WireGuard VPN servers with traffic obfuscation (via WireGuard Obfuscator) support. It provides an intuitive web UI and REST API for managing WireGuard clients, configuring obfuscation settings, and monitoring server statistics.

This project integrates with [WireGuard Obfuscator](https://github.com/ClusterM/wg-obfuscator) to help bypass ISP and government restrictions on WireGuard traffic.

> **Note:** This application is designed to run exclusively as a Docker container. It is not intended to run directly on the host system.

## Features

- 🌐 **Web-based Management Interface** - Modern, responsive UI built with React and TypeScript
- 🔐 **Client Management** - Create, edit, delete, and manage WireGuard clients with automatic client configuration generation
- 📊 **Real-time Statistics** - Monitor server status, client connections, and traffic statistics
- 🛡️ **Traffic Obfuscation** - Configure and manage WireGuard Obfuscator for bypassing DPI restrictions
- 🔒 **Secure Authentication** - Token-based authentication with login rate limiting
- 📱 **Multi-language Support** - English and Russian interfaces
- 🐳 **Docker-Only** - Designed exclusively for Docker containers
- 🚀 **Easy Installation** - One-command automated installation script
- 🔒 **HTTPS Support** - Automatic SSL certificate management with Caddy (via installation script)
- 📡 **REST API** - Full OpenAPI 3.0 specification for integration

## Installation

### Automated Installation

The easiest way to get started is using the automated installation script:
```bash
wget https://bit.ly/wg-obf -O install.sh && bash install.sh
```

The installation script will:
1. Check for root privileges
2. Install Docker and required packages
3. Detect your server's external IP address
4. Generate random configuration values (admin password, web prefix, ports)
5. Pull and run the Docker container
6. Offer HTTPS via Let's Encrypt: an IP certificate by default, or your own domain if it already points to the server
7. Install and configure Caddy (outside the container) for HTTPS with automatic SSL certificates
8. Display access information and credentials

After installation, you'll receive:
- HTTP URL to the control panel
- HTTPS URL (IP by default, or your domain if you chose one)
- Admin username and password

> **Note:** Caddy is installed outside the Docker container only when using the automated installation script. For manual Docker installations, you'll need to set up HTTPS separately or access the container directly via HTTP.

### Manual Docker Installation

If you prefer manual setup without the automated script:

```bash
docker run -d \
  --name wg-obf-easy \
  -v ~/.wg-obf-easy:/config \
  -e TZ=Europe/Moscow \
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
- HTTPS: Terminate TLS in an external reverse proxy (Caddy, Nginx, Traefik, etc.) or use the automated installation script, which installs and configures Caddy automatically outside the container.

### Environment Variables

- `WEB_PREFIX` - Web interface path prefix (e.g., `/vpn/`)
- `EXTERNAL_IP` - Server address given to clients. Can be an IPv4 address or a domain name (including DDNS). Used as-is in Endpoint and obfuscator `target`. When generating an obfuscated WireGuard config, domain names are resolved to A records so those `/32` addresses can be excluded from AllowedIPs (unless the client keeps the server in AllowedIPs). A downloaded config will not update if the domain later points to a new IP.
- `EXTERNAL_PORT` - Port written into client configs (WG Endpoint and obfuscator `target`)
- `LISTEN_PORT` - Initial UDP port the container listens on (obfuscator, or WireGuard when obfuscation is off). Used only if `listen_port` is not already stored in the database. If unset or if `listen_port` is `null`, the container listens on `EXTERNAL_PORT`. Map Docker UDP as `-p <listen>:<listen>/udp`; DNAT/port forwards on the router should target this port. Change later via `GET`/`PATCH /api/config` (`listen_port`; `null` means follow `EXTERNAL_PORT`).
  > **Note:** changing `listen_port` through the API only changes the port inside the container. Docker port publishing (`-p`) is fixed when the container is created, so the new port stays unreachable until you recreate the container with a matching `-p <listen>:<listen>/udp` (`install.sh` publishes `EXTERNAL_PORT` only). Use it when a reverse proxy or manual port mapping already forwards traffic to that port.
- `TZ` - Container timezone (e.g., `Europe/Moscow`). Optional; can also be set in the web UI
- `ADMIN_USERNAME` - Admin username, applied on first start only (default: `admin`)
- `ADMIN_PASSWORD` - Admin password (default: `admin`)
- `AUTH_ENABLED` - Enable/disable authentication (default: `true`)
- `LOG_LEVEL` - Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (default: `INFO`)
- `FLASK_DEBUG` - Use the Flask development server instead of waitress (default: `false`)
- `WAITRESS_THREADS` - Thread count for the waitress production server (default: `8`)

## Usage

You do not need to know how WireGuard works to use this panel. After installation, open the URL the installer printed, create a client, and import the configs on the phone or computer.

### Open the panel

**After the automated installer:**
- HTTP: `http://your-server-ip/your-prefix/`
- HTTPS: `https://your-server-ip/your-prefix/` (or your domain, if you chose one)

**After a manual Docker run:**
- HTTP: `http://your-server-ip:5000/your-prefix/`

Log in with the username and password from the installer (default username is `admin`). Change the password on the **Configuration** page as soon as you can.

At the top of every page:
- A switch that starts or stops the VPN server — leave it on
- Light / dark theme
- Language (English or Russian)
- Logout

There are three tabs: **Dashboard**, **Clients**, and **Configuration**.

### Connect a device

1. Open **Clients** and click **Add Client**.
2. Type a name (for example `phone`) and click **Create**. Leave **Enable** checked.
3. Click the new client in the list.
4. Copy a config or show its **QR Code**, then import it on the device.

Obfuscation is **on** by default. The device then needs two pieces:

- **WireGuard Obfuscator config** — install [WireGuard Obfuscator](https://github.com/ClusterM/wg-obfuscator) on the device and load this config. It hides WireGuard traffic so filters that block WireGuard often miss it.
- **WireGuard config** — install the official [WireGuard](https://www.wireguard.com/) app and import this config. WireGuard talks to the obfuscator on the same device, not to the internet directly.

If you turn obfuscation **off** on the Configuration page, you only need the WireGuard app and the WireGuard config.

If **Allow non-obfuscated connections** is enabled, the client card shows both paths: a plain WireGuard config, and the obfuscated pair.

When the device is online, the client row shows **Connected**. The Dashboard also shows how many clients are online.

If you change that client's settings, the obfuscation key, or the server keys, import the new configs on the device again. Old files will stop working.

### Dashboard

This is the status page. It refreshes by itself.

- **WireGuard** / **Obfuscator** — should say **Running** while the server is on
- **Clients connected/total**
- **External IP** and **External Port** — address and port written into client configs (an IPv4 address or a domain name)
- **Server IP** — the server's own address inside the VPN
- **Subnet** — private address range given to clients
- **Public Key** — the server's WireGuard public key
- **Recent Logs** — last messages from the obfuscator; look here if a client cannot connect

### Clients

Each row is one device. Click a row to open details, keys, traffic, and configs.

- **Enable / disable** — a disabled client cannot connect
- **Delete** — removes the client; its old config stops working
- **Regenerate Keys** — creates new keys for that client; the device must import a new config

#### Client settings

These options only change the generated config for that device. They do not change how the server itself runs. Leave the defaults if you are not sure.

- **Enable preshared key** — optional extra shared secret for this client. Stronger, but the key must be in the client's config. Generate one or paste an existing WireGuard key.
- **Override Masking Type** — disguise traffic as another protocol for this client only. **Use Default** follows the server setting. This control is unavailable if **Disallow Other Masking** is on.
- **Obfuscator Port** — port on the *device* between WireGuard and the obfuscator (not the public server port). Change it only if that port is already used on the phone or PC.
- **Allowed IP Addresses** — which destinations go through the VPN. `0.0.0.0/0` means "all internet traffic". Use a smaller subnet only if you want some traffic to stay outside the VPN.
- **Do not exclude the server address from AllowedIPs** — leave this off. The panel already excludes the server address so the connection does not loop. Turn it on only if you handle that another way.
- **Obfuscator Log Verbosity Level** — how detailed the obfuscator logs are on the device. Raise it only when debugging.

### Configuration

After you edit **General Settings**, click **Save**.

#### General settings

- **Subnet** — private network for VPN clients, always with a `/24` mask (for example `10.66.66.0/24`). Change it only if those addresses already exist on the clients' own networks.
- **Enable Obfuscation** — recommended. Off means plain WireGuard only, which is easier for an ISP to block.
- **Allow non-obfuscated connections** — accept both obfuscated and plain WireGuard on the same port. Useful if some devices cannot run the obfuscator.
- **Obfuscation Key** — shared secret used by obfuscation. Every client config includes it. If you change it, **every** device needs a new obfuscator config. Click **Generate** for a random key.
- **Default Masking** — `NONE` (obfuscated, no extra disguise) or `STUN` (looks more like video-call traffic). If WireGuard is blocked, try `STUN`.
- **Disallow Other Masking** — clients cannot pick a different masking type.
- **Obfuscator Log Verbosity Level** — how detailed the **server** logs are (shown on the Dashboard). `INFO` is fine for daily use.

#### WireGuard server keys

Shows the server public key. **Regenerate Server Keys** breaks every existing client until they import new configs. Do not press this unless you know you need new keys.

#### Prometheus metrics token

Optional. Only if you scrape metrics with Prometheus. Generate a token, then send `Authorization: Bearer <token>` to `/api/metrics/...`. Most users can ignore this.

#### System timezone

Affects timestamps in logs only. It does not change VPN behavior.

#### Admin credentials

Change the panel username and/or password. You must enter the current password. After a change you will be asked to log in again.

## Docker Images

Docker images are available on Docker Hub: **`clustermeerkat/wg-obf-easy`**

### Available Tags

- `latest` - Latest stable release
- `nightly` - Latest build from the master branch (may be unstable)
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

## REST API

### API Endpoints

The full API documentation is the OpenAPI 3.0 file [`api.yaml`](api.yaml) in this repository. Open it in Swagger UI, Redoc, or any other OpenAPI viewer for request parameters, bodies, and responses.

Overview of the endpoint groups:

- **Authentication**: `/api/auth/login` - Login and get an access token
- **Clients**: `/api/clients/*` - Client management (CRUD operations)
- **Configuration**: `/api/config/*` - Server configuration
- **Statistics**: `/api/stats/*` - Server and client statistics
- **Metrics**: `/api/metrics/*` - Prometheus-compatible metrics (requires an access token or a metrics token). Includes overall service status and client statuses.
- **Health**: `/health` - Health check endpoint

### Authentication

Most API endpoints require authentication. Include the access token in the `Authorization` header:

```
Authorization: Bearer <your-access-token>
```

#### Metrics Token

Metrics endpoints under `/api/metrics/*` also accept a dedicated metrics token. Use the `/api/metrics/token` resource to manage it:

- `GET /api/metrics/token` — returns the current token (or `null` if not set)
- `POST /api/metrics/token` — generates a new token, replacing the previous one
- `DELETE /api/metrics/token` — deletes the token

Include the token in Prometheus scrape jobs via the standard `Authorization: Bearer <token>` header.

### Rate Limiting

- Login endpoint: 5 attempts per minute per IP
- Other API endpoints are not rate limited by default; configure rate limiting at your reverse proxy if required

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
     -e TZ=Europe/Moscow \
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
- **Rate limiting** - Login is limited to 5 attempts per minute per IP; other API endpoints are not rate-limited by default
- **Authentication** - Access tokens expire after 24 hours
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
- Certificates are obtained automatically via Let's Encrypt (IP by default, or a domain that already points to the server)
- Check Caddy logs: `journalctl -u caddy`
- For a domain certificate, verify DNS resolution for your domain
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
