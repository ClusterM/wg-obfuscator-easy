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
#   wget https://bit.ly/wg-obf -O install.sh && bash install.sh
#
# IMPORTANT: This script must be run interactively (not through a pipe).
#            It will guide you through all configuration steps.
#

set -e
#set -x

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Default language
LANG_CHOICE="en"

# Language strings - English
declare -A MSG_EN=(
    [SELECT_LANG_TITLE]="Language selection / Выбор языка"
    [SELECT_LANG]="Select language / Выберите язык"
    [LANG_EN]="English"
    [LANG_RU]="Русский"
    [INSTALL_FAILED]="Installation failed at line %s. Please check the error messages above."
    [INSTALLING_CURL]="Installing curl..."
    [INSTALLING_SYSTEMD]="Installing systemd..."
    [OS_DETECT_ERROR]="Unable to detect OS for curl installation"
    [OS_DETECT_ERROR_SYSTEMD]="Unable to detect OS for systemd installation"
    [DOCKER_INSTALLED]="Docker is already installed"
    [INSTALLING_DOCKER]="Installing Docker..."
    [REMOVING_PODMAN]="Removing podman-docker to avoid conflicts with Docker CE..."
    [ADDING_DOCKER_REPO]="Adding official Docker CE repository..."
    [DOCKER_INSTALL_FAILED]="Docker installation failed"
    [OS_DETECT_ERROR_DOCKER]="Unable to detect OS for Docker installation"
    [DOCKER_INSTALLED_SUCCESS]="Docker installed successfully"
    [FIREWALL_PORT_OPENED]="Firewall: port %s opened"
    [FIREWALL_PORT_ALREADY_OPEN]="Firewall: port %s already open in %s"
    [FIREWALL_NOT_ACTIVE]="firewalld detected but not running. Skipping automatic opening of %s."
    [FIREWALL_FAILED_RUNTIME]="Failed to open %s in firewalld runtime configuration."
    [FIREWALL_FAILED_PERMANENT]="Failed to add %s to firewalld permanent configuration."
    [UFW_INACTIVE]="UFW detected but inactive. Port %s was not modified."
    [UFW_FAILED]="Failed to allow %s via UFW."
    [IPTABLES_NOT_AVAILABLE]="iptables command not available to open %s."
    [IPTABLES_FAILED]="Failed to add iptables rule for %s."
    [FIREWALL_NO_BACKEND]="No supported firewall backend detected. Please ensure port %s is reachable."
    [IPTABLES_PERSISTENCE_NETFILTER]="Configuring iptables persistence using netfilter-persistent..."
    [IPTABLES_PERSISTENCE_SERVICES]="Configuring iptables persistence using iptables-services..."
    [IPTABLES_PERSISTENCE_OPENRC]="Configuring iptables persistence using iptables-openrc..."
    [IPTABLES_PERSISTENCE_UNSUPPORTED]="Automatic iptables persistence is not supported for OS: %s. Please configure rule saving manually."
    [IPTABLES_RULES_SAVED]="iptables rules saved for persistence."
    [IPTABLES_PERSISTENCE_CONFIGURED]="iptables persistence configured and current rules saved."
    [IPTABLES_PERSISTENCE_FAILED]="Failed to confirm iptables rule persistence. Please verify manually."
    [FIREWALLD_RELOADED]="firewalld reloaded to apply permanent firewall changes."
    [FIREWALLD_RELOAD_FAILED]="Failed to reload firewalld. Please reload it manually to apply changes."
    [CADDY_INSTALLED]="Caddy is already installed"
    [INSTALLING_CADDY]="Installing Caddy..."
    [INSTALLING_CADDY_SCRIPT]="Installing Caddy using official script..."
    [CADDY_INSTALL_FAILED]="Caddy installation failed"
    [CADDY_INSTALLED_SUCCESS]="Caddy installed successfully"
    [CADDY_CONFIGURING]="Configuring Caddy HTTP reverse proxy for host: %s"
    [CADDY_TARGET_PORT]="Configuring Caddy for target port: %s (proxying to %s)"
    [CADDY_BACKUP]="Backing up existing Caddyfile to %s"
    [CADDY_DOMAIN_SETUP]="Configuring Caddy domain with Let's Encrypt SSL certificate..."
    [CADDY_CONFIG_VALID]="Caddyfile configuration is valid"
    [CADDY_VALIDATION_FAILED]="Caddyfile validation failed, but continuing..."
    [CADDY_RELOADING]="Reloading Caddy configuration..."
    [CADDY_RELOADED]="Caddy configuration reloaded"
    [CADDY_RELOAD_FAILED]="Caddy reload failed or timed out, restarting..."
    [CADDY_STARTING]="Starting Caddy service..."
    [CADDY_NO_SYSTEMCTL]="systemctl not available, trying to start Caddy directly..."
    [CADDY_WAIT_SSL]="Waiting for Caddy to start and obtain SSL certificate (this may take up to 30 seconds)..."
    [CADDY_WAIT_START]="Waiting for Caddy to start (this may take up to 30 seconds)..."
    [CADDY_RUNNING]="Caddy is running"
    [CADDY_NOT_RUNNING_SYSTEMCTL]="Caddy service may not be running properly. Check logs with: journalctl -u caddy"
    [CADDY_NOT_RUNNING]="Caddy may not be running properly. Check Caddy logs."
    [DOMAIN_REQUIRED]="Domain is required for HTTPS configuration"
    [SCRIPT_REQUIRES_INTERACTIVE]="================================================"
    [SCRIPT_REQUIRES_INTERACTIVE2]="This script requires interactive mode!"
    [SCRIPT_REQUIRES_INTERACTIVE3]="You cannot run this script through a pipe (curl ... | bash)."
    [SCRIPT_DOWNLOAD_DIRECT]="Please download and run it directly:"
    [SCRIPT_OR_WGET]="Or use wget:"
    [SCRIPT_TITLE]="================================================"
    [SCRIPT_TITLE2]="WireGuard Obfuscator Easy - Installation Script"
    [SCRIPT_GUIDE]="This script will guide you through the installation process."
    [SCRIPT_QUESTIONS]="You will be asked a few questions to configure your setup."
    [SCRIPT_REQUIRES_ROOT]="This script must be run as root. Re-launching with sudo. You may be prompted for your password."
    [SCRIPT_REQUIRES_ROOT2]="This script must be run as root"
    [SCRIPT_RUN_AS_ROOT]="Please run as root (for example, with sudo if available):"
    [DETECTED_OS]="Detected OS: %s"
    [DETECTED_FIREWALL]="Detected firewall manager: %s"
    [FIREWALL_INACTIVE]="Firewall manager detected (%s) but appears inactive."
    [NO_FIREWALL]="No supported firewall manager detected."
    [INSTALLING_PACKAGES]="Installing required packages... (this may take a while)"
    [SYSTEMCTL_NOT_INSTALLED]="systemctl is not installed. Please install it and try again."
    [SYSTEMCTL_TRY]="Try: systemctl start docker"
    [DOCKER_NOT_RUNNING]="Docker is installed but not running. Please start Docker and try again."
    [DETECTING_IP]="Detecting external IP address..."
    [IP_DETECT_FAILED]="Failed to detect external IP address"
    [EXTERNAL_IP]="External IP: %s"
    [OLD_CONFIG_FOUND]="Old configuration found. Do you want to keep old settings? (Y/n): "
    [CONFIG_DIR]="Config directory: %s"
    [PULLING_IMAGE]="Pulling Docker image: %s..."
    [PULL_FAILED]="Failed to pull Docker image. Make sure the image exists and you have internet connection."
    [STARTING_CONTAINER]="Starting WireGuard Obfuscator Easy Docker container..."
    [CONTAINER_START_FAILED]="Failed to start Docker container"
    [CONTAINER_WAITING]="Waiting for container to be ready..."
    [CONTAINER_RUNNING]="Container is running"
    [CONTAINER_FAILED]="Container failed to start. Check logs with: docker logs %s"
    [APP_WAITING]="Waiting for application to be ready..."
    [APP_RESPONDING]="Application is responding"
    [APP_NOT_READY]="Application may not be fully ready yet. It should be available shortly."
    [GETTING_VERSION]="Getting application version..."
    [APP_VERSION]="Application version: v%s"
    [INSTALLED_VERSION_OLD]="Previously installed version: v%s"
    [VERSION_UNKNOWN]="Could not determine application version"
    [ENABLE_HTTPS_PROMPT]="Do you want to enable HTTPS (recommended)? It requires a domain name, but you can use a free domain name. (Y/n): "
    [NEED_GUIDE_DUCKDNS]="Do you need a guide how to obtain a free domain name from DuckDNS? (Y/n/q): "
    [DUCKDNS_GUIDE_INTRO]="We'll use DuckDNS to create a free domain name for your server."
    [DUCKDNS_YOUR_IP]="Your server IP address is: %s"
    [DUCKDNS_STEPS]="Follow these steps to set up DuckDNS:"
    [DUCKDNS_STEP1]="1. Open your web browser and go to: https://www.duckdns.org/"
    [DUCKDNS_STEP2]="2. Click on 'Sign in with Google' or 'Sign in with GitHub'"
    [DUCKDNS_STEP2_NOTE]="   (You can use any Google or GitHub account - it's free)"
    [DUCKDNS_STEP3]="3. After signing in, you'll see a page where you must:"
    [DUCKDNS_STEP3_1]="   - Enter a new subdomain name (e.g., any name you want, but it must be unique and not already taken)"
    [DUCKDNS_STEP3_2]="   - Enter your server IP address: %s"
    [DUCKDNS_STEP3_3]="   - Click 'add domain' or 'update ip'"
    [DUCKDNS_ENTER_SUBDOMAIN]="After creating your DuckDNS domain, enter your DuckDNS subdomain name (or enter 'q' to cancel and continue without HTTPS)."
    [DUCKDNS_EXAMPLE]="Example: If your domain is 'myvpn.duckdns.org', enter 'myvpn'."
    [DUCKDNS_SUBDOMAIN_PROMPT]="DuckDNS subdomain: "
    [SUBDOMAIN_EMPTY]="Subdomain cannot be empty. Please enter your DuckDNS subdomain."
    [SUBDOMAIN_INVALID]="Invalid subdomain. Use only letters, numbers, and hyphens."
    [ENTER_DOMAIN]="Enter your domain name (or enter 'q' to cancel and continue without HTTPS): "
    [DOMAIN_EMPTY]="Domain cannot be empty. Please enter your domain name."
    [DOMAIN_INVALID]="Invalid domain name."
    [CHECKING_DNS]="Checking if domain %s points to your IP address (%s)..."
    [DNS_CONFIGURED]="DNS is correctly configured! Domain %s points to %s."
    [DNS_WAITING]="Waiting for DNS to propagate... (attempt %s/%s)"
    [DNS_VERIFY_FAILED]="Could not verify DNS configuration automatically. Please check your DNS settings."
    [DNS_DUCKDNS_NOTE]="If you are using DuckDNS, please make sure you have added your domain and your server IP address."
    [DNS_PROPAGATION_NOTE]="It's possible that your DNS is not propagated yet. Please wait some time and try again. Some DNS providers take up to 24 hours to propagate."
    [CONTINUE_WITHOUT_HTTPS]="Let's continue without HTTPS for now."
    [SSL_SETUP]="SSL Certificate Setup"
    [SSL_LETSENCRYPT]="Let's Encrypt will automatically provide SSL certificates for your domain."
    [SSL_EMAIL_INFO]="You can optionally provide an email address to receive notifications"
    [SSL_EMAIL_INFO2]="when your certificate is about to expire (certificates are renewed automatically)."
    [SSL_EMAIL_OPTIONAL]="This email is completely optional - SSL certificates will work without it."
    [EMAIL_PROMPT]="Enter email address for notifications (or press Enter to skip): "
    [EMAIL_SKIPPED]="Continuing without email. SSL certificates will still work perfectly."
    [EMAIL_SET]="Email set: %s"
    [EMAIL_NOTIFICATIONS]="You'll receive notifications about certificate expiration (if any)."
    [EMAIL_INVALID]="Invalid email format!"
    [EMAIL_INVALID_FORMAT]="Please enter a valid email address (e.g., user@example.com)"
    [EMAIL_SKIP_NOTE]="or press Enter without typing anything to skip."
    [HTTPS_SETUP]="Setting up HTTPS with Caddy..."
    [HTTPS_FAILED]="HTTPS setup failed. Let's continue without HTTPS."
    [HTTP_PROXY_SETUP]="Setting up HTTP reverse proxy with Caddy on port 80..."
    [HTTP_PROXY_FAILED]="Failed to configure HTTP reverse proxy with Caddy. HTTP will remain available on port %s."
    [HTTP_PROXY_SUCCESS]="Caddy HTTP reverse proxy configured successfully."
    [INSTALL_COMPLETE]="================================================"
    [INSTALL_COMPLETE2]="Installation completed successfully!"
    [INSTALLED_VERSION]="Installed version: v%s"
    [FIREWALL_OPENED_PORTS]="Firewall (%s) opened ports: %s"
    [FIREWALL_MANUAL_PORTS]="Firewall ports requiring manual configuration: %s"
    [UFW_NOT_APPLIED]="UFW rules were not applied automatically because UFW is inactive."
    [FIREWALLD_NOT_APPLIED]="firewalld rules were not applied automatically because the service is not running."
    [CONFIGURATION]="Configuration:"
    [CONTAINER_NAME]="  Container name: %s"
    [WIREGUARD_PORT]="  WireGuard port: %s"
    [WEB_PREFIX]="  Web prefix: %s"
    [HTTPS_ENABLED]="  HTTPS enabled: %s"
    [HTTP_URL]="HTTP URL: %s (not recommended - use HTTPS)"
    [HTTPS_URL]="HTTPS URL: %s (using Let's Encrypt certificate)"
    [HTTP_URL_SIMPLE]="HTTP URL: %s"
    [RESET_PASSWORD_PROMPT]="Do you want to reset current password?"
    [LOGIN_CREDENTIALS]="Login Credentials:"
    [USERNAME]="  Username: admin"
    [PASSWORD]="  Password: %s"
    [LOGIN_SAME]="Login Credentials are the same as the ones you used to install the script."
    [CERT_WAIT]="It can some time for the certificate to be obtained. If you cannot access the web interface, please wait a few minutes and try again."
    [SAVE_CREDENTIALS]="Save these credentials in a secure location!"
    [HTTPS_NOT_ENABLED]="HTTPS is not enabled. You can enable it later by running the script again."
    [DB_NOT_FOUND]="Database file not found: %s"
    [CONTAINER_NOT_FOUND_RESET]="Container %s not found."
    [CONTAINER_STARTING_TEMP]="Container is not running. Starting temporarily to reset password..."
    [CONTAINER_START_FAILED_RESET]="Failed to start container."
    [ADMIN_RESET_FAILED]="Failed to update administrator database."
    [ADMIN_RESET_SUCCESS]="Administrator credentials have been reset."
    [ADMIN_NEW_LOGIN]="New login: admin"
    [ADMIN_NEW_PASSWORD]="New password: %s"
    [TOKENS_DELETED]="All active access tokens have been deleted. Users need to log in again."
    [PRESS_ENTER]="Press Enter to continue..."
)

# Language strings - Russian
declare -A MSG_RU=(
    [SELECT_LANG_TITLE]="Language selection / Выбор языка"
    [SELECT_LANG]="Select language / Выберите язык"
    [LANG_EN]="English"
    [LANG_RU]="Русский"
    [INSTALL_FAILED]="Установка не удалась на строке %s. Проверьте сообщения об ошибках выше."
    [INSTALLING_CURL]="Установка curl..."
    [INSTALLING_SYSTEMD]="Установка systemd..."
    [OS_DETECT_ERROR]="Не удалось определить ОС для установки curl"
    [OS_DETECT_ERROR_SYSTEMD]="Не удалось определить ОС для установки systemd"
    [DOCKER_INSTALLED]="Docker уже установлен"
    [INSTALLING_DOCKER]="Установка Docker..."
    [REMOVING_PODMAN]="Удаление podman-docker во избежание конфликтов с Docker CE..."
    [ADDING_DOCKER_REPO]="Добавление официального репозитория Docker CE..."
    [DOCKER_INSTALL_FAILED]="Не удалось установить Docker"
    [OS_DETECT_ERROR_DOCKER]="Не удалось определить ОС для установки Docker"
    [DOCKER_INSTALLED_SUCCESS]="Docker успешно установлен"
    [FIREWALL_PORT_OPENED]="Файрвол: порт %s открыт"
    [FIREWALL_PORT_ALREADY_OPEN]="Файрвол: порт %s уже открыт в %s"
    [FIREWALL_NOT_ACTIVE]="firewalld обнаружен, но не запущен. Пропуск автоматического открытия %s."
    [FIREWALL_FAILED_RUNTIME]="Не удалось открыть %s в runtime конфигурации firewalld."
    [FIREWALL_FAILED_PERMANENT]="Не удалось добавить %s в постоянную конфигурацию firewalld."
    [UFW_INACTIVE]="UFW обнаружен, но неактивен. Порт %s не был изменён."
    [UFW_FAILED]="Не удалось разрешить %s через UFW."
    [IPTABLES_NOT_AVAILABLE]="Команда iptables недоступна для открытия %s."
    [IPTABLES_FAILED]="Не удалось добавить правило iptables для %s."
    [FIREWALL_NO_BACKEND]="Не обнаружено поддерживаемого файрвола. Убедитесь, что порт %s доступен."
    [IPTABLES_PERSISTENCE_NETFILTER]="Настройка сохранения правил iptables с помощью netfilter-persistent..."
    [IPTABLES_PERSISTENCE_SERVICES]="Настройка сохранения правил iptables с помощью iptables-services..."
    [IPTABLES_PERSISTENCE_OPENRC]="Настройка сохранения правил iptables с помощью iptables-openrc..."
    [IPTABLES_PERSISTENCE_UNSUPPORTED]="Автоматическое сохранение правил iptables не поддерживается для ОС: %s. Настройте сохранение правил вручную."
    [IPTABLES_RULES_SAVED]="Правила iptables сохранены для постоянного использования."
    [IPTABLES_PERSISTENCE_CONFIGURED]="Сохранение правил iptables настроено, текущие правила сохранены."
    [IPTABLES_PERSISTENCE_FAILED]="Не удалось подтвердить сохранение правил iptables. Проверьте вручную."
    [FIREWALLD_RELOADED]="firewalld перезагружен для применения постоянных изменений."
    [FIREWALLD_RELOAD_FAILED]="Не удалось перезагрузить firewalld. Перезагрузите его вручную для применения изменений."
    [CADDY_INSTALLED]="Caddy уже установлен"
    [INSTALLING_CADDY]="Установка Caddy..."
    [INSTALLING_CADDY_SCRIPT]="Установка Caddy с помощью официального скрипта..."
    [CADDY_INSTALL_FAILED]="Не удалось установить Caddy"
    [CADDY_INSTALLED_SUCCESS]="Caddy успешно установлен"
    [CADDY_CONFIGURING]="Настройка HTTP обратного прокси Caddy для хоста: %s"
    [CADDY_TARGET_PORT]="Настройка Caddy для целевого порта: %s (проксирование на %s)"
    [CADDY_BACKUP]="Создание резервной копии Caddyfile в %s"
    [CADDY_DOMAIN_SETUP]="Настройка домена Caddy с SSL-сертификатом Let's Encrypt..."
    [CADDY_CONFIG_VALID]="Конфигурация Caddyfile корректна"
    [CADDY_VALIDATION_FAILED]="Проверка Caddyfile не удалась, но продолжаем..."
    [CADDY_RELOADING]="Перезагрузка конфигурации Caddy..."
    [CADDY_RELOADED]="Конфигурация Caddy перезагружена"
    [CADDY_RELOAD_FAILED]="Перезагрузка Caddy не удалась или превышено время ожидания, перезапуск..."
    [CADDY_STARTING]="Запуск сервиса Caddy..."
    [CADDY_NO_SYSTEMCTL]="systemctl недоступен, пробуем запустить Caddy напрямую..."
    [CADDY_WAIT_SSL]="Ожидание запуска Caddy и получения SSL-сертификата (это может занять до 30 секунд)..."
    [CADDY_WAIT_START]="Ожидание запуска Caddy (это может занять до 30 секунд)..."
    [CADDY_RUNNING]="Caddy запущен"
    [CADDY_NOT_RUNNING_SYSTEMCTL]="Сервис Caddy может работать некорректно. Проверьте логи: journalctl -u caddy"
    [CADDY_NOT_RUNNING]="Caddy может работать некорректно. Проверьте логи Caddy."
    [DOMAIN_REQUIRED]="Для настройки HTTPS требуется доменное имя"
    [SCRIPT_REQUIRES_INTERACTIVE]="================================================"
    [SCRIPT_REQUIRES_INTERACTIVE2]="Этот скрипт требует интерактивного режима!"
    [SCRIPT_REQUIRES_INTERACTIVE3]="Вы не можете запустить этот скрипт через pipe (curl ... | bash)."
    [SCRIPT_DOWNLOAD_DIRECT]="Пожалуйста, скачайте и запустите его напрямую:"
    [SCRIPT_OR_WGET]="Или используйте wget:"
    [SCRIPT_TITLE]="================================================"
    [SCRIPT_TITLE2]="WireGuard Obfuscator Easy - Скрипт установки"
    [SCRIPT_GUIDE]="Этот скрипт проведёт вас через процесс установки."
    [SCRIPT_QUESTIONS]="Вам будет задано несколько вопросов для настройки."
    [SCRIPT_REQUIRES_ROOT]="Этот скрипт должен выполняться от имени root. Перезапуск с sudo. Вас могут попросить ввести пароль."
    [SCRIPT_REQUIRES_ROOT2]="Этот скрипт должен выполняться от имени root"
    [SCRIPT_RUN_AS_ROOT]="Пожалуйста, запустите от имени root (например, с помощью sudo, если доступно):"
    [DETECTED_OS]="Обнаружена ОС: %s"
    [DETECTED_FIREWALL]="Обнаружен менеджер файрвола: %s"
    [FIREWALL_INACTIVE]="Обнаружен менеджер файрвола (%s), но он неактивен."
    [NO_FIREWALL]="Не обнаружено поддерживаемого менеджера файрвола."
    [INSTALLING_PACKAGES]="Установка необходимых пакетов... (это может занять некоторое время)"
    [SYSTEMCTL_NOT_INSTALLED]="systemctl не установлен. Пожалуйста, установите его и попробуйте снова."
    [SYSTEMCTL_TRY]="Попробуйте: systemctl start docker"
    [DOCKER_NOT_RUNNING]="Docker установлен, но не запущен. Пожалуйста, запустите Docker и попробуйте снова."
    [DETECTING_IP]="Определение внешнего IP-адреса..."
    [IP_DETECT_FAILED]="Не удалось определить внешний IP-адрес"
    [EXTERNAL_IP]="Внешний IP: %s"
    [OLD_CONFIG_FOUND]="Найдена старая конфигурация. Хотите сохранить старые настройки? (Y/n): "
    [CONFIG_DIR]="Директория конфигурации: %s"
    [PULLING_IMAGE]="Загрузка Docker-образа: %s..."
    [PULL_FAILED]="Не удалось загрузить Docker-образ. Убедитесь, что образ существует и у вас есть подключение к интернету."
    [STARTING_CONTAINER]="Запуск Docker-контейнера WireGuard Obfuscator Easy..."
    [CONTAINER_START_FAILED]="Не удалось запустить Docker-контейнер"
    [CONTAINER_WAITING]="Ожидание готовности контейнера..."
    [CONTAINER_RUNNING]="Контейнер запущен"
    [CONTAINER_FAILED]="Контейнер не запустился. Проверьте логи: docker logs %s"
    [APP_WAITING]="Ожидание готовности приложения..."
    [APP_RESPONDING]="Приложение отвечает"
    [APP_NOT_READY]="Приложение может быть ещё не полностью готово. Оно должно стать доступным в ближайшее время."
    [GETTING_VERSION]="Получение версии приложения..."
    [APP_VERSION]="Версия приложения: v%s"
    [INSTALLED_VERSION_OLD] = "Установленная до этого версия: v%s"
    [VERSION_UNKNOWN]="Не удалось определить версию приложения"
    [ENABLE_HTTPS_PROMPT]="Хотите включить HTTPS (рекомендуется)? Требуется доменное имя, но вы можете использовать бесплатный домен. (Y/n): "
    [NEED_GUIDE_DUCKDNS]="Нужна инструкция, как получить бесплатный домен от DuckDNS? (Y/n/q): "
    [DUCKDNS_GUIDE_INTRO]="Мы используем DuckDNS для создания бесплатного доменного имени для вашего сервера."
    [DUCKDNS_YOUR_IP]="IP-адрес вашего сервера: %s"
    [DUCKDNS_STEPS]="Следуйте этим шагам для настройки DuckDNS:"
    [DUCKDNS_STEP1]="1. Откройте веб-браузер и перейдите на: https://www.duckdns.org/"
    [DUCKDNS_STEP2]="2. Нажмите 'Sign in with Google' или 'Sign in with GitHub'"
    [DUCKDNS_STEP2_NOTE]="   (Вы можете использовать любой аккаунт Google или GitHub - это бесплатно)"
    [DUCKDNS_STEP3]="3. После входа вы увидите страницу, где нужно:"
    [DUCKDNS_STEP3_1]="   - Ввести новое имя поддомена (например, любое имя, но оно должно быть уникальным и не занятым)"
    [DUCKDNS_STEP3_2]="   - Ввести IP-адрес вашего сервера: %s"
    [DUCKDNS_STEP3_3]="   - Нажать 'add domain' или 'update ip'"
    [DUCKDNS_ENTER_SUBDOMAIN]="После создания домена DuckDNS введите имя вашего поддомена DuckDNS (или введите 'q' для отмены и продолжения без HTTPS)."
    [DUCKDNS_EXAMPLE]="Пример: Если ваш домен 'myvpn.duckdns.org', введите 'myvpn'."
    [DUCKDNS_SUBDOMAIN_PROMPT]="Поддомен DuckDNS: "
    [SUBDOMAIN_EMPTY]="Поддомен не может быть пустым. Пожалуйста, введите ваш поддомен DuckDNS."
    [SUBDOMAIN_INVALID]="Некорректный поддомен. Используйте только буквы, цифры и дефисы."
    [ENTER_DOMAIN]="Введите ваше доменное имя (или введите 'q' для отмены и продолжения без HTTPS): "
    [DOMAIN_EMPTY]="Домен не может быть пустым. Пожалуйста, введите ваше доменное имя."
    [DOMAIN_INVALID]="Некорректное доменное имя."
    [CHECKING_DNS]="Проверка, указывает ли домен %s на ваш IP-адрес (%s)..."
    [DNS_CONFIGURED]="DNS настроен правильно! Домен %s указывает на %s."
    [DNS_WAITING]="Ожидание распространения DNS... (попытка %s/%s)"
    [DNS_VERIFY_FAILED]="Не удалось автоматически проверить конфигурацию DNS. Пожалуйста, проверьте настройки DNS."
    [DNS_DUCKDNS_NOTE]="Если вы используете DuckDNS, убедитесь, что вы добавили свой домен и IP-адрес сервера."
    [DNS_PROPAGATION_NOTE]="Возможно, ваш DNS ещё не распространился. Подождите некоторое время и попробуйте снова. Некоторым DNS-провайдерам требуется до 24 часов для распространения."
    [CONTINUE_WITHOUT_HTTPS]="Продолжим без HTTPS пока что."
    [SSL_SETUP]="Настройка SSL-сертификата"
    [SSL_LETSENCRYPT]="Let's Encrypt автоматически предоставит SSL-сертификаты для вашего домена."
    [SSL_EMAIL_INFO]="Вы можете опционально указать адрес электронной почты для получения уведомлений,"
    [SSL_EMAIL_INFO2]="когда ваш сертификат истекает (сертификаты продлеваются автоматически)."
    [SSL_EMAIL_OPTIONAL]="Этот email полностью опционален - SSL-сертификаты будут работать и без него."
    [EMAIL_PROMPT]="Введите адрес электронной почты для уведомлений (или нажмите Enter для пропуска): "
    [EMAIL_SKIPPED]="Продолжение без email. SSL-сертификаты будут отлично работать."
    [EMAIL_SET]="Email установлен: %s"
    [EMAIL_NOTIFICATIONS]="Вы будете получать уведомления об истечении сертификата (если они будут)."
    [EMAIL_INVALID]="Некорректный формат email!"
    [EMAIL_INVALID_FORMAT]="Пожалуйста, введите корректный адрес email (например, user@example.com)"
    [EMAIL_SKIP_NOTE]="или нажмите Enter, не вводя ничего, для пропуска."
    [HTTPS_SETUP]="Настройка HTTPS с Caddy..."
    [HTTPS_FAILED]="Настройка HTTPS не удалась. Продолжим без HTTPS."
    [HTTP_PROXY_SETUP]="Настройка HTTP обратного прокси Caddy на порту 80..."
    [HTTP_PROXY_FAILED]="Не удалось настроить HTTP обратный прокси Caddy. HTTP останется доступным на порту %s."
    [HTTP_PROXY_SUCCESS]="HTTP обратный прокси Caddy успешно настроен."
    [INSTALL_COMPLETE]="================================================"
    [INSTALL_COMPLETE2]="Установка успешно завершена!"
    [INSTALLED_VERSION]="Установленная версия: v%s"
    [FIREWALL_OPENED_PORTS]="Файрвол (%s) открыл порты: %s"
    [FIREWALL_MANUAL_PORTS]="Порты файрвола, требующие ручной настройки: %s"
    [UFW_NOT_APPLIED]="Правила UFW не были применены автоматически, так как UFW неактивен."
    [FIREWALLD_NOT_APPLIED]="Правила firewalld не были применены автоматически, так как сервис не запущен."
    [CONFIGURATION]="Конфигурация:"
    [CONTAINER_NAME]="  Имя контейнера: %s"
    [WIREGUARD_PORT]="  Порт WireGuard: %s"
    [WEB_PREFIX]="  Веб-префикс: %s"
    [HTTPS_ENABLED]="  HTTPS включён: %s"
    [HTTP_URL]="HTTP URL: %s (не рекомендуется - используйте HTTPS)"
    [HTTPS_URL]="HTTPS URL: %s (используется сертификат Let's Encrypt)"
    [HTTP_URL_SIMPLE]="HTTP URL: %s"
    [RESET_PASSWORD_PROMPT]="Хотите сбросить текущий пароль?"
    [LOGIN_CREDENTIALS]="Учётные данные для входа:"
    [USERNAME]="  Имя пользователя: admin"
    [PASSWORD]="  Пароль: %s"
    [LOGIN_SAME]="Учётные данные для входа те же, что вы использовали при установке скрипта."
    [CERT_WAIT]="Получение сертификата может занять некоторое время. Если вы не можете получить доступ к веб-интерфейсу, подождите несколько минут и попробуйте снова."
    [SAVE_CREDENTIALS]="Сохраните эти учётные данные в безопасном месте!"
    [HTTPS_NOT_ENABLED]="HTTPS не включён. Вы можете включить его позже, запустив скрипт снова."
    [DB_NOT_FOUND]="Файл базы данных не найден: %s"
    [CONTAINER_NOT_FOUND_RESET]="Контейнер %s не найден."
    [CONTAINER_STARTING_TEMP]="Контейнер не запущен. Запускаю временно для сброса пароля..."
    [CONTAINER_START_FAILED_RESET]="Не удалось запустить контейнер."
    [ADMIN_RESET_FAILED]="Не удалось обновить базу данных администратора."
    [ADMIN_RESET_SUCCESS]="Учётные данные администратора сброшены."
    [ADMIN_NEW_LOGIN]="Новый логин: admin"
    [ADMIN_NEW_PASSWORD]="Новый пароль: %s"
    [TOKENS_DELETED]="Все активные токены доступа удалены. Пользователям нужно войти заново."
    [PRESS_ENTER]="Нажмите Enter для продолжения..."
)

# Function to get localized message
msg() {
    local key=$1
    shift
    local template
    
    if [ "$LANG_CHOICE" = "ru" ]; then
        template="${MSG_RU[$key]}"
    else
        template="${MSG_EN[$key]}"
    fi
    
    if [ $# -gt 0 ]; then
        printf "$template" "$@"
    else
        echo "$template"
    fi
}

# Trap to handle errors (only for critical failures)
trap 'print_error "$(msg INSTALL_FAILED $LINENO)"' ERR INT TERM

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
    print_info "$(msg INSTALLING_CURL)"
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
        print_error "$(msg OS_DETECT_ERROR)"
        exit 1
    fi
}

install_systemd() {
    print_info "$(msg INSTALLING_SYSTEMD)"
    if [ "$OS" = "debian" ] || [ "$OS" = "ubuntu" ]; then
        apt-get update -qq
        apt-get install -y systemd
    elif [ "$OS" = "rhel" ] || [ "$OS" = "centos" ] || [ "$OS" = "fedora" ]; then
        dnf install -y systemd
    elif [ "$OS" = "alpine" ]; then
        apk add --no-cache systemd
    else
        print_error "$(msg OS_DETECT_ERROR_SYSTEMD)"
        exit 1
    fi
}

# Function to install Docker
install_docker() {
    if command_exists docker; then
        print_info "$(msg DOCKER_INSTALLED)"
        return
    fi

    print_info "$(msg INSTALLING_DOCKER)"
    
    if [ "$OS" = "debian" ] || [ "$OS" = "ubuntu" ]; then
        # Install Docker using official script
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        rm get-docker.sh
    elif [ "$OS" = "rhel" ] || [ "$OS" = "centos" ] || [ "$OS" = "fedora" ]; then
        local docker_packages="docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin"
        if command_exists dnf; then
            if rpm -q podman-docker >/dev/null 2>&1; then
                print_warning "$(msg REMOVING_PODMAN)"
                dnf remove -y podman-docker >/dev/null
            fi
            dnf install -y dnf-plugins-core
            if ! dnf repolist 2>/dev/null | grep -q "^docker-ce-stable"; then
                print_info "$(msg ADDING_DOCKER_REPO)"
                dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo >/dev/null
            fi
            dnf install -y $docker_packages
        else
            if rpm -q podman-docker >/dev/null 2>&1; then
                print_warning "$(msg REMOVING_PODMAN)"
                yum remove -y podman-docker >/dev/null
            fi
            yum install -y yum-utils
            if ! yum repolist 2>/dev/null | grep -q "^docker-ce-stable"; then
                print_info "$(msg ADDING_DOCKER_REPO)"
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
        print_error "$(msg OS_DETECT_ERROR_DOCKER)"
        exit 1
    fi

    # Verify Docker installation
    if ! command_exists docker; then
        print_error "$(msg DOCKER_INSTALL_FAILED)"
        exit 1
    fi

    print_info "$(msg DOCKER_INSTALLED_SUCCESS)"
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
        print_info "$(msg FIREWALL_PORT_OPENED "$spec")"
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
                print_info "$(msg IPTABLES_PERSISTENCE_NETFILTER)"
                export DEBIAN_FRONTEND=noninteractive
                apt-get update -qq
                apt-get install -y netfilter-persistent iptables-persistent
                install_performed=true
                ;;
            rhel|centos|fedora)
                print_info "$(msg IPTABLES_PERSISTENCE_SERVICES)"
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
                print_info "$(msg IPTABLES_PERSISTENCE_OPENRC)"
                apk add --no-cache iptables ip6tables iptables-openrc
                rc-update add iptables default >/dev/null 2>&1 || true
                rc-update add ip6tables default >/dev/null 2>&1 || true
                install_performed=true
                ;;
            *)
                print_warning "$(msg IPTABLES_PERSISTENCE_UNSUPPORTED "$OS")"
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
            print_info "$(msg IPTABLES_PERSISTENCE_CONFIGURED)"
        else
            print_info "$(msg IPTABLES_RULES_SAVED)"
        fi
    else
        print_warning "$(msg IPTABLES_PERSISTENCE_FAILED)"
    fi
}

open_firewall_port() {
    local port=$1
    local protocol=${2:-tcp}
    local spec="${port}/${protocol}"

    case "$FIREWALL_BACKEND" in
        firewalld)
            if [ "$FIREWALL_BACKEND_STATE" != "active" ]; then
                print_warning "$(msg FIREWALL_NOT_ACTIVE "$spec")"
                record_firewall_result "$spec" "skipped" FIREWALL_PORTS_SKIPPED
                return
            fi

            local runtime_added=false
            local permanent_added=false

            if ! firewall-cmd --query-port="$spec" >/dev/null 2>&1; then
                if firewall-cmd --add-port="$spec" >/dev/null 2>&1; then
                    runtime_added=true
                else
                    print_warning "$(msg FIREWALL_FAILED_RUNTIME "$spec")"
                fi
            fi

            if ! firewall-cmd --permanent --query-port="$spec" >/dev/null 2>&1; then
                if firewall-cmd --permanent --add-port="$spec" >/dev/null 2>&1; then
                    permanent_added=true
                    FIREWALL_RELOAD_REQUIRED=true
                else
                    print_warning "$(msg FIREWALL_FAILED_PERMANENT "$spec")"
                fi
            fi

            if [ "$runtime_added" = true ] || [ "$permanent_added" = true ]; then
                record_firewall_result "$spec" "opened" FIREWALL_PORTS_OPENED
            else
                print_info "$(msg FIREWALL_PORT_ALREADY_OPEN "$spec" "firewalld")"
            fi
            ;;
        ufw)
            local status_line
            status_line=$(ufw status 2>/dev/null | head -n1 || echo "")
            if echo "$status_line" | grep -qi "inactive"; then
                print_warning "$(msg UFW_INACTIVE "$spec")"
                record_firewall_result "$spec" "skipped" FIREWALL_PORTS_SKIPPED
                return
            fi

            if ufw status numbered 2>/dev/null | grep -qw "$spec"; then
                print_info "$(msg FIREWALL_PORT_ALREADY_OPEN "$spec" "UFW")"
                return
            fi

            if ufw allow "$spec" >/dev/null 2>&1; then
                record_firewall_result "$spec" "opened" FIREWALL_PORTS_OPENED
            else
                print_warning "$(msg UFW_FAILED "$spec")"
                record_firewall_result "$spec" "skipped" FIREWALL_PORTS_SKIPPED
            fi
            ;;
        iptables)
            if ! command_exists iptables; then
                record_firewall_result "$spec" "skipped" FIREWALL_PORTS_SKIPPED
                print_warning "$(msg IPTABLES_NOT_AVAILABLE "$spec")"
                return
            fi

            if ! iptables -C INPUT -p "$protocol" --dport "$port" -j ACCEPT >/dev/null 2>&1; then
                if iptables -I INPUT -p "$protocol" --dport "$port" -j ACCEPT >/dev/null 2>&1; then
                    record_firewall_result "$spec" "opened" FIREWALL_PORTS_OPENED
                else
                    print_warning "$(msg IPTABLES_FAILED "$spec")"
                    record_firewall_result "$spec" "skipped" FIREWALL_PORTS_SKIPPED
                fi
            else
                print_info "$(msg FIREWALL_PORT_ALREADY_OPEN "$spec" "iptables")"
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
            print_warning "$(msg FIREWALL_NO_BACKEND "$spec")"
            ;;
    esac
}

finalize_firewall_changes() {
    if [ "$FIREWALL_BACKEND" = "firewalld" ] && [ "$FIREWALL_BACKEND_STATE" = "active" ] && [ "$FIREWALL_RELOAD_REQUIRED" = true ]; then
        if firewall-cmd --reload >/dev/null 2>&1; then
            print_info "$(msg FIREWALLD_RELOADED)"
            FIREWALL_RELOAD_REQUIRED=false
        else
            print_warning "$(msg FIREWALLD_RELOAD_FAILED)"
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
        print_info "$(msg CADDY_INSTALLED)"
        return
    fi

    print_info "$(msg INSTALLING_CADDY)"
    
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
        print_info "$(msg INSTALLING_CADDY_SCRIPT)"
        curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/setup.rpm.sh' | bash
        if command_exists dnf; then
            dnf install -y caddy
        else
            yum install -y caddy
        fi
    fi

    # Verify Caddy installation
    if ! command_exists caddy; then
        print_error "$(msg CADDY_INSTALL_FAILED)"
        exit 1
    fi

    print_info "$(msg CADDY_INSTALLED_SUCCESS)"
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

reset_admin_credentials() {
    local provided_password=$1
    local started_temporarily="false"
    local db_path="$CONFIG_DIR/wg-easy.db"
    
    # Check if password is provided
    if [ -z "$provided_password" ]; then
        print_error "$(msg ADMIN_RESET_FAILED)" >&2
        return 1
    fi
    
    # Check if database file exists
    if [ ! -f "$db_path" ]; then
        print_error "$(msg DB_NOT_FOUND "$db_path")" >&2
        return 1
    fi

    # Detect container state
    detect_container_state
    
    # Check if container exists
    if [ "$CONTAINER_EXISTS" != "true" ]; then
        print_error "$(msg CONTAINER_NOT_FOUND_RESET "$CONTAINER_NAME")" >&2
        return 1
    fi

    # Start container if not running
    if [ "$CONTAINER_RUNNING" != "true" ]; then
        print_info "$(msg CONTAINER_STARTING_TEMP)" >&2
        if ! docker start "$CONTAINER_NAME" >/dev/null 2>&1; then
            print_error "$(msg CONTAINER_START_FAILED_RESET)" >&2
            return 1
        fi
        started_temporarily="true"
        # Wait for container to be ready
        sleep 2
    fi

    # Update database with new credentials
    local python_output
    local python_exit_code
    
    python_output=$(docker exec "$CONTAINER_NAME" /usr/bin/env python3 - "$provided_password" <<'PY' 2>&1
import sqlite3
import sys
import hashlib
from datetime import datetime

try:
    password = sys.argv[1]
    if not password:
        print("Error: Password is empty", file=sys.stderr)
        sys.exit(1)
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    now = datetime.now().isoformat()
    
    db_path = "/config/wg-easy.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Update admin username
        cursor.execute("""
            INSERT INTO config (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=?, updated_at=?
        """, ("admin_username", "admin", now, "admin", now))
        
        # Update admin password hash
        cursor.execute("""
            INSERT INTO config (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=?, updated_at=?
        """, ("admin_password_hash", password_hash, now, password_hash, now))
        
        # Delete all tokens
        cursor.execute("DELETE FROM tokens")
        
        conn.commit()
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}", file=sys.stderr)
        sys.exit(1)
        
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
PY
    )
    python_exit_code=$?
    
    if [ $python_exit_code -ne 0 ]; then
        print_error "$(msg ADMIN_RESET_FAILED)" >&2
        if [ -n "$python_output" ]; then
            echo "$python_output" >&2
        fi
        # Stop container if we started it temporarily
        if [ "$started_temporarily" = "true" ]; then
            docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
        fi
        return 1
    fi

    # Stop container if we started it temporarily
    if [ "$started_temporarily" = "true" ]; then
        docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
    fi
    
    return 0
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
            print_error "$(msg DOMAIN_REQUIRED)"
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
        print_info "$(msg CADDY_CONFIGURING "$site_label")"
    fi

    print_info "$(msg CADDY_TARGET_PORT "$http_port" "$web_prefix")"

    # Backup existing Caddyfile if it exists
    if [ -f "$caddyfile" ]; then
        print_info "$(msg CADDY_BACKUP "${caddyfile}.backup")"
        cp "$caddyfile" "${caddyfile}.backup"
    fi

    if [ "$mode" = "https" ]; then
        print_info "$(msg CADDY_DOMAIN_SETUP)"
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
        print_info "$(msg CADDY_CONFIG_VALID)"
    else
        print_warning "$(msg CADDY_VALIDATION_FAILED)"
    fi
    
    # Reload or restart Caddy
    if command_exists systemctl; then
        if systemctl is-active --quiet caddy 2>/dev/null; then
            print_info "$(msg CADDY_RELOADING)"
            # Use timeout to prevent hanging on reload
            # If reload fails or hangs, fall back to restart
            if timeout 10 systemctl reload caddy 2>/dev/null; then
                print_info "$(msg CADDY_RELOADED)"
            else
                print_warning "$(msg CADDY_RELOAD_FAILED)"
                systemctl restart caddy
            fi
        else
            print_info "$(msg CADDY_STARTING)"
            systemctl enable caddy 2>/dev/null || true
            systemctl start caddy
        fi
    else
        # Fallback: try to start Caddy directly
        print_warning "$(msg CADDY_NO_SYSTEMCTL)"
        caddy run --config "$caddyfile" &
    fi
    
    # Wait a bit for Caddy to start and, if needed, obtain certificate
    if [ "$mode" = "https" ]; then
        print_info "$(msg CADDY_WAIT_SSL)"
    else
        print_info "$(msg CADDY_WAIT_START)"
    fi
    sleep 5
    
    # Check if Caddy is running
    local max_attempts=6
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if command_exists systemctl; then
            if systemctl is-active --quiet caddy 2>/dev/null; then
                print_info "$(msg CADDY_RUNNING)"
                return 0
            fi
        else
            # Check if Caddy process is running
            if pgrep -x caddy >/dev/null 2>&1; then
                print_info "$(msg CADDY_RUNNING)"
                return 0
            fi
        fi
        sleep 5
        attempt=$((attempt + 1))
    done
    
    if command_exists systemctl; then
        print_warning "$(msg CADDY_NOT_RUNNING_SYSTEMCTL)"
    else
        print_warning "$(msg CADDY_NOT_RUNNING)"
    fi
    return 1
}

# Main installation function
main() {
    # Check if we can read from stdin (interactive mode required)
    if ! [ -t 0 ]; then
        print_error "$(msg SCRIPT_REQUIRES_INTERACTIVE)"
        print_error "$(msg SCRIPT_REQUIRES_INTERACTIVE2)"
        print_error "$(msg SCRIPT_REQUIRES_INTERACTIVE)"
        echo ""
        print_error "$(msg SCRIPT_REQUIRES_INTERACTIVE3)"
        echo ""
        print_info "$(msg SCRIPT_DOWNLOAD_DIRECT)"
        echo ""
        print_info "  curl -Ls https://raw.githubusercontent.com/ClusterM/wg-obfuscator-easy/master/install.sh -o install.sh"
        print_info "  bash install.sh"
        echo ""
        print_info "$(msg SCRIPT_OR_WGET)"
        print_info "  wget https://raw.githubusercontent.com/ClusterM/wg-obfuscator-easy/master/install.sh"
        print_info "  bash install.sh"
        echo ""
        exit 1
    fi
    
    # Language selection (restore from environment if running through sudo)
    if [ -n "$WG_OBF_LANG" ]; then
        LANG_CHOICE="$WG_OBF_LANG"
    else
        echo ""
        echo "$(msg SELECT_LANG_TITLE)"
        echo "  1) $(msg LANG_EN) (default)"
        echo "  2) $(msg LANG_RU)"
        echo ""
        read -p "$(msg SELECT_LANG): " -r lang_choice
        if [ -z "$lang_choice" ]; then
            lang_choice=1
        fi
        case "$lang_choice" in
            2)
                LANG_CHOICE="ru"
                ;;
            *)
                LANG_CHOICE="en"
                ;;
        esac
        echo ""
    fi
    
    print_info "$(msg SCRIPT_TITLE)"
    print_info "$(msg SCRIPT_TITLE2)"
    print_info "$(msg SCRIPT_TITLE)"
    echo ""
    print_info "$(msg SCRIPT_GUIDE)"
    print_info "$(msg SCRIPT_QUESTIONS)"
    echo ""
    
    # Check if running as root
    if [ "$EUID" -ne 0 ]; then
        if command_exists sudo; then
            print_warning "$(msg SCRIPT_REQUIRES_ROOT)"
            exec sudo WG_OBF_LANG="$LANG_CHOICE" bash "$0" "$@"
        else
            print_error "$(msg SCRIPT_REQUIRES_ROOT2)"
            echo ""
            print_info "$(msg SCRIPT_RUN_AS_ROOT)"
            print_info "  sudo bash install.sh"
            echo ""
            exit 1
        fi
    fi

    CONFIG_EXISTS=false
    KEEP_OLD_HOST_CONFIG=false
    OLD_APP_VERSION=""
    if [ -f "$CONFIG_FILE" ]; then
        OLD_APP_VERSION=$(get_app_version "$CONTAINER_NAME")
        CONFIG_EXISTS=true
        ADMIN_PASSWORD=""
        while true; do
            read -p "$(msg OLD_CONFIG_FOUND)" -r
            if [[ -z "$REPLY" ]] || [[ "$REPLY" =~ ^[Yy]$ ]]; then
                source "$CONFIG_FILE"
                KEEP_OLD_HOST_CONFIG=true
                break
            elif [[ "$REPLY" =~ ^[Nn]$ ]]; then
                break
            fi
        done
        echo ""
    fi
    if [ "$KEEP_OLD_HOST_CONFIG" = false ]; then
        WEB_PREFIX="/$(generate_prefix)/"
    fi
    ADMIN_PASSWORD=$(generate_password)

    # Detect OS
    detect_os
    print_info "$(msg DETECTED_OS "$OS")"

    detect_firewall_backend
    if [ "$FIREWALL_BACKEND" != "none" ]; then
        if [ "$FIREWALL_BACKEND_STATE" = "active" ]; then
            print_info "$(msg DETECTED_FIREWALL "$FIREWALL_BACKEND")"
        else
            print_warning "$(msg FIREWALL_INACTIVE "$FIREWALL_BACKEND")"
        fi
    else
        print_info "$(msg NO_FIREWALL)"
    fi

    print_info "$(msg INSTALLING_PACKAGES)"

    if ! command_exists systemctl; then
        # Install systemd if needed
        install_systemd
        if ! command_exists systemctl; then
            print_error "$(msg SYSTEMCTL_NOT_INSTALLED)"
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
        print_error "$(msg DOCKER_NOT_RUNNING)"
        if command_exists systemctl; then
            print_info "$(msg SYSTEMCTL_TRY)"
        fi
        exit 1
    fi
    
    # Get external IP
    print_info "$(msg DETECTING_IP)"
    EXTERNAL_IP=$(get_external_ip)
    if [ -z "$EXTERNAL_IP" ]; then
        print_error "$(msg IP_DETECT_FAILED)"
        exit 1
    fi
    print_info "$(msg EXTERNAL_IP "$EXTERNAL_IP")"

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

    if [ "$KEEP_OLD_HOST_CONFIG" = false ]; then
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
        WIREGUARD_PORT=$(generate_port)
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
    fi
    
    # Create config directory
    mkdir -p "$CONFIG_DIR"
    print_info "$(msg CONFIG_DIR "$CONFIG_DIR")"

    # Remove existing container if it exists to free the ports
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        docker rm "$CONTAINER_NAME" 1>/dev/null || true
    fi

    # Pull Docker image
    print_info "$(msg PULLING_IMAGE "$IMAGE_NAME")"
    docker pull "$IMAGE_NAME" 1>/dev/null || {
        print_error "$(msg PULL_FAILED)"
        exit 1
    }

    # Run Docker container
    print_info "$(msg STARTING_CONTAINER)"
    docker run -d \
        --name "$CONTAINER_NAME" \
        -v "$CONFIG_DIR:/config" \
        -e WEB_PREFIX="$WEB_PREFIX" \
        -e EXTERNAL_IP="$EXTERNAL_IP" \
        -e EXTERNAL_PORT="$WIREGUARD_PORT" \
        -e ADMIN_PASSWORD="$ADMIN_PASSWORD" \
        -e LOG_LEVEL=DEBUG \
        -p "${WIREGUARD_PORT}:${WIREGUARD_PORT}/udp" \
        -p "${HTTP_PORT}:5000/tcp" \
        --cap-add NET_ADMIN \
        --cap-add SYS_MODULE \
        --sysctl net.ipv4.ip_forward=1 \
        --sysctl net.ipv4.conf.all.src_valid_mark=1 \
        --restart unless-stopped \
        "$IMAGE_NAME" 1>/dev/null || {
        print_error "$(msg CONTAINER_START_FAILED)"
        exit 1
    }
    
    # Wait for container to be ready
    print_info "$(msg CONTAINER_WAITING)"
    sleep 5
    
    # Check if container is running
    local max_wait=30
    local wait_time=0
    while [ $wait_time -lt $max_wait ]; do
        if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
            print_info "$(msg CONTAINER_RUNNING)"
            break
        fi
        sleep 2
        wait_time=$((wait_time + 2))
    done
    
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        print_error "$(msg CONTAINER_FAILED "$CONTAINER_NAME")"
        exit 1
    fi
    
    # Wait a bit more for the application to be ready
    print_info "$(msg APP_WAITING)"
    sleep 5
    
    # Check if application is responding
    local max_health_checks=10
    local health_check=0
    while [ $health_check -lt $max_health_checks ]; do
        if curl -s -f -o /dev/null "http://localhost:$HTTP_PORT$WEB_PREFIX" 2>/dev/null || \
            curl -s -f -o /dev/null "http://127.0.0.1:$HTTP_PORT$WEB_PREFIX" 2>/dev/null; then
            print_info "$(msg APP_RESPONDING)"
            break
        fi
        sleep 2
        health_check=$((health_check + 1))
    done
    if [ $health_check -eq $max_health_checks ]; then
        print_warning "$(msg APP_NOT_READY)"
    fi
    
    # Get application version from container
    print_info "$(msg GETTING_VERSION)"
    APP_VERSION=$(get_app_version "$CONTAINER_NAME")
    if [ "$APP_VERSION" != "unknown" ]; then
        if [ -n "$OLD_APP_VERSION" ]; then
            print_info "$(msg INSTALLED_VERSION_OLD "$OLD_APP_VERSION")"
        fi
        print_info "$(msg APP_VERSION "$APP_VERSION")"
    else
        print_warning "$(msg VERSION_UNKNOWN)"
        APP_VERSION=""
    fi    

    if [ "$KEEP_OLD_HOST_CONFIG" = false ]; then
        while true; do
            read -p "$(msg ENABLE_HTTPS_PROMPT)" -r
            if [[ -z "$REPLY" ]] || [[ "$REPLY" =~ ^[Yy]$ ]]; then
                ENABLE_HTTPS=true
                break
            elif [[ "$REPLY" =~ ^[Nn]$ ]]; then
                ENABLE_HTTPS=false
                break
            fi
        done

        DOMAIN=""
        if [ "$ENABLE_HTTPS" = true ]; then
            # TODO: check reverse DNS for the domain, which should point to the server IP address
            while true; do
                read -p "$(msg NEED_GUIDE_DUCKDNS)" -r
                if [[ "$REPLY" =~ ^[Qq]$ ]]; then
                    ENABLE_HTTPS=false
                    break
                elif [[ -z "$REPLY" ]] || [[ "$REPLY" =~ ^[Yy]$ ]]; then
                    echo ""
                    print_info "$(msg DUCKDNS_GUIDE_INTRO)"
                    print_info "$(msg DUCKDNS_YOUR_IP "$EXTERNAL_IP")"
                    echo ""
                    print_info "$(msg DUCKDNS_STEPS)"
                    echo ""
                    print_info "$(msg DUCKDNS_STEP1)"
                    echo ""
                    print_info "$(msg DUCKDNS_STEP2)"
                    print_info "$(msg DUCKDNS_STEP2_NOTE)"
                    echo ""
                    print_info "$(msg DUCKDNS_STEP3)"
                    print_info "$(msg DUCKDNS_STEP3_1)"
                    print_info "$(msg DUCKDNS_STEP3_2 "$EXTERNAL_IP")"
                    print_info "$(msg DUCKDNS_STEP3_3)"
                    echo ""
                    # Get DuckDNS subdomain
                    while true; do
                        print_info "$(msg DUCKDNS_ENTER_SUBDOMAIN)"
                        print_info "$(msg DUCKDNS_EXAMPLE)"
                        echo ""
                        read -p "$(msg DUCKDNS_SUBDOMAIN_PROMPT)" -r
                        if [[ "$REPLY" =~ ^[Qq]$ ]]; then
                            ENABLE_HTTPS=false
                            break
                        fi
                        local duckdns_subdomain="$REPLY"
                        if [ -z "$duckdns_subdomain" ]; then
                            print_error "$(msg SUBDOMAIN_EMPTY)"
                            echo ""
                            continue
                        fi
                        # Basic validation - only alphanumeric and hyphens
                        if ! echo "$duckdns_subdomain" | grep -qE '^[a-zA-Z0-9-]+$'; then
                            print_error "$(msg SUBDOMAIN_INVALID)"
                            echo ""
                            continue
                        fi
                        DOMAIN="${duckdns_subdomain}.duckdns.org"
                        break
                    done
                    break
                elif [[ "$REPLY" =~ ^[Nn]$ ]]; then
                    while true; do
                        read -p "$(msg ENTER_DOMAIN)" -r
                        if [[ "$REPLY" =~ ^[Qq]$ ]]; then
                            ENABLE_HTTPS=false
                            break
                        fi
                        DOMAIN="$REPLY"
                        if [ -z "$DOMAIN" ]; then
                            print_error "$(msg DOMAIN_EMPTY)"
                            echo ""
                            continue
                        fi
                        if ! echo "$DOMAIN" | grep -qE '^[a-zA-Z0-9\.-]+\.[a-zA-Z]{2,}$'; then
                            print_error "$(msg DOMAIN_INVALID)"
                            echo ""
                            continue
                        fi
                        break
                    done
                    break
                fi
            done
        fi
    fi

    DNS_RESOLVED=false
    if [ "$ENABLE_HTTPS" = true ]; then
        print_info "$(msg CHECKING_DNS "$DOMAIN" "$EXTERNAL_IP")"
        
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
                print_info "$(msg DNS_CONFIGURED "$DOMAIN" "$EXTERNAL_IP")"
                break
            fi
            
            print_info "$(msg DNS_WAITING "$((dns_check + 1))" "$max_dns_checks")"
            sleep 10
            dns_check=$((dns_check + 1))
        done
        
        if [ "$DNS_RESOLVED" = false ]; then
            print_warning "$(msg DNS_VERIFY_FAILED)"
            print_warning "$(msg DNS_DUCKDNS_NOTE)"
            print_warning "$(msg DNS_PROPAGATION_NOTE)"
            print_info "$(msg CONTINUE_WITHOUT_HTTPS)"
            ENABLE_HTTPS=false
        elif [ "$KEEP_OLD_HOST_CONFIG" = false ]; then
            print_info "$(msg SSL_SETUP)"
            print_info "$(msg SSL_LETSENCRYPT)"
            print_info "$(msg SSL_EMAIL_INFO)"
            print_info "$(msg SSL_EMAIL_INFO2)"
            print_info "$(msg SSL_EMAIL_OPTIONAL)"
            while true; do
                read -p "$(msg EMAIL_PROMPT)" -r
                if [ -z "$REPLY" ]; then
                    # Empty email - that's fine
                    ACME_EMAIL=""
                    print_info "$(msg EMAIL_SKIPPED)"
                    break
                elif echo "$REPLY" | grep -qE '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'; then
                    # Valid email
                    ACME_EMAIL="$REPLY"
                    print_info "$(msg EMAIL_SET "$ACME_EMAIL")"
                    print_info "$(msg EMAIL_NOTIFICATIONS)"
                    break
                else
                    print_error "$(msg EMAIL_INVALID)"
                    print_error "$(msg EMAIL_INVALID_FORMAT)"
                    print_error "$(msg EMAIL_SKIP_NOTE)"
                fi
            done
        fi
    fi

    # Open firewall ports
    open_firewall_port "$WIREGUARD_PORT" "udp"
    open_firewall_port "80" "tcp"
    open_firewall_port "443" "tcp"

    # Install and configure Caddy if HTTPS is enabled
    HTTP_PORT_REAL=$HTTP_PORT
    if [ "$ENABLE_HTTPS" = true ]; then
        print_info "$(msg HTTPS_SETUP)"
        
        # Configure Caddy
        if ! configure_caddy "$DOMAIN" "$HTTP_PORT" "$WEB_PREFIX" "https"; then
            print_warning "$(msg HTTPS_FAILED)"
            systemctl stop caddy
            systemctl disable caddy
            ENABLE_HTTPS=false
        fi
    fi
    if [ "$ENABLE_HTTPS" = false ]; then
        # check if the 80 port is in use
        if ! check_port "80"; then
            print_info "$(msg HTTP_PROXY_SETUP)"
            local http_proxy_host
            http_proxy_host="$DOMAIN"
            if [ -z "$http_proxy_host" ]; then
                http_proxy_host=":80"
            fi
            if ! configure_caddy "$http_proxy_host" "$HTTP_PORT" "$WEB_PREFIX" "http"; then
                print_warning "$(msg HTTP_PROXY_FAILED "$HTTP_PORT")"
                open_firewall_port "$HTTP_PORT" "tcp"
                systemctl stop caddy
                systemctl disable caddy
            else
                print_info "$(msg HTTP_PROXY_SUCCESS)"
                HTTP_PORT=80
            fi
        fi
    fi

    finalize_firewall_changes

    # Print summary
    echo ""
    print_info "$(msg INSTALL_COMPLETE)"
    print_info "$(msg INSTALL_COMPLETE2)"
    if [ -n "$APP_VERSION" ]; then
        print_info "$(msg INSTALLED_VERSION "$APP_VERSION")"
    fi
    print_info "$(msg INSTALL_COMPLETE)"
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
            print_info "$(msg FIREWALL_OPENED_PORTS "$FIREWALL_BACKEND" "$opened_ports")"
        fi
        if [ -n "$skipped_ports" ]; then
            print_warning "$(msg FIREWALL_MANUAL_PORTS "$skipped_ports")"
        fi

        if [ "$FIREWALL_BACKEND" = "ufw" ] && [ "$FIREWALL_BACKEND_STATE" != "active" ]; then
            print_warning "$(msg UFW_NOT_APPLIED)"
        fi
        if [ "$FIREWALL_BACKEND" = "firewalld" ] && [ "$FIREWALL_BACKEND_STATE" != "active" ]; then
            print_warning "$(msg FIREWALLD_NOT_APPLIED)"
        fi
        echo ""
    fi

    NEW_PASSWORD=false
    while true; do
        read -p "$(msg RESET_PASSWORD_PROMPT)" -r
        if [[ "$REPLY" =~ ^[Yy]$ ]]; then
            if reset_admin_credentials "$ADMIN_PASSWORD"; then
                # Function succeeded
                NEW_PASSWORD=true
                break
            else
                # Function failed, show error and continue loop
                print_error "$(msg ADMIN_RESET_FAILED)"
                read -p "$(msg PRESS_ENTER)" || true
                # Continue loop to ask again
            fi
        elif [[ -z "$REPLY" ]] || [[ "$REPLY" =~ ^[Nn]$ ]]; then
            break
        fi
    done

    print_info "$(msg CONFIGURATION)"
    print_info "$(msg CONTAINER_NAME "$CONTAINER_NAME")"
    print_info "$(msg WIREGUARD_PORT "$WIREGUARD_PORT")"
    print_info "$(msg WEB_PREFIX "$WEB_PREFIX")"
    if [ "$ENABLE_HTTPS" = true ]; then
        print_info "$(msg HTTPS_ENABLED "true")"
    else
        print_info "$(msg HTTPS_ENABLED "false")"
    fi
    echo ""

    if [ "$ENABLE_HTTPS" = true ]; then
        print_info "$(msg HTTP_URL "http://$DOMAIN$WEB_PREFIX")"
        print_info "$(msg HTTPS_URL "https://$DOMAIN$WEB_PREFIX")"
    else
        if [ "$HTTP_PORT" = 80 ]; then
            print_info "$(msg HTTP_URL_SIMPLE "http://$EXTERNAL_IP$WEB_PREFIX")"
        else
            print_info "$(msg HTTP_URL_SIMPLE "http://$EXTERNAL_IP:$HTTP_PORT$WEB_PREFIX")"
        fi
    fi
    echo ""

    if [ "$CONFIG_EXISTS" = false ] || [ "$NEW_PASSWORD" = true ]; then
        print_info "$(msg LOGIN_CREDENTIALS)"
        print_info "$(msg USERNAME)"
        print_info "$(msg PASSWORD "$ADMIN_PASSWORD")"
    else
        print_info "$(msg LOGIN_SAME)"
    fi
    echo ""
    
    if [ "$ENABLE_HTTPS" = true ]; then
        print_warning "$(msg CERT_WAIT)"
    fi
    print_warning "$(msg SAVE_CREDENTIALS)"
    if [ "$ENABLE_HTTPS" = false ]; then
        print_warning "$(msg HTTPS_NOT_ENABLED)"
    fi
    
    # Save configuration to file
    cat > "$CONFIG_FILE" <<EOF
DOMAIN="$DOMAIN"
ENABLE_HTTPS="$ENABLE_HTTPS"
HTTP_PORT="$HTTP_PORT_REAL"
WEB_PREFIX="$WEB_PREFIX"
WIREGUARD_PORT="$WIREGUARD_PORT"
ACME_EMAIL="$ACME_EMAIL"
EOF
}

# Run main function
main "$@"

