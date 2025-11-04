# WireGuard Obfuscator Easy API

REST API для управления WireGuard сервером с поддержкой обфускации трафика через `wg-obfuscator`.

## Возможности

- ✅ Управление клиентами WireGuard (добавление, удаление, редактирование)
- ✅ Генерация конфигурационных файлов для клиентов
- ✅ Управление обфускацией трафика
- ✅ Мониторинг статуса WireGuard и обфускатора
- ✅ Статистика подключений и трафика
- ✅ Token-based аутентификация (OAuth 2.0 Bearer tokens)
- ✅ Автоматическое применение изменений конфигурации
- ✅ Graceful shutdown всех сервисов
- ✅ Управление состоянием клиентов (включение/выключение)
- ✅ Просмотр логов обфускатора

## Структура проекта

```
/app
├── app/                    # Основной пакет приложения
│   ├── config/            # Управление конфигурацией
│   ├── auth/              # Аутентификация и авторизация
│   ├── wireguard/         # Управление WireGuard
│   ├── obfuscator/        # Управление обфускатором
│   ├── clients/           # Управление клиентами
│   ├── api/               # Flask API endpoints
│   ├── services.py        # Оркестрация сервисов
│   ├── utils.py           # Утилиты
│   ├── exceptions.py      # Кастомные исключения
│   └── main.py            # Точка входа
├── frontend/              # React frontend приложение
├── wg-easy.db            # SQLite база данных (конфигурация, клиенты, токены)
└── requirements.txt       # Зависимости Python
```

## Установка и запуск

### Требования

- Python 3.8+
- WireGuard (`wg`, `wg-quick`)
- `wg-obfuscator` (опционально, если используется обфускация)

### Установка зависимостей

```bash
pip install -r requirements.txt
```

### Переменные окружения

```bash
# Обязательные
EXTERNAL_PORT=57159          # Порт для WireGuard

# Опциональные
EXTERNAL_IP=1.2.3.4          # Внешний IP (если не указан, будет получен автоматически)
ADMIN_USERNAME=admin         # Имя администратора (по умолчанию: admin)
ADMIN_PASSWORD=admin         # Пароль администратора (по умолчанию: admin)
AUTH_ENABLED=true            # Включить авторизацию (по умолчанию: true)
```

### Запуск

```bash
python -m app.main
# или
python main.py
```

API будет доступен по адресу `http://localhost:5000`

---

## API Документация

### Базовый URL

Все API endpoints находятся по адресу `/api/*`, кроме health check: `/health`

### Аутентификация

API использует OAuth 2.0 Bearer Token аутентификацию. Все защищенные endpoints требуют заголовок:

```
Authorization: Bearer <token>
```

Токен можно получить через `/api/auth/login`. По умолчанию токены действуют 24 часа.

---

## Endpoints

### 🔐 Аутентификация

#### POST `/api/auth/login`

Авторизация и получение токена доступа.

**Аутентификация:** Не требуется

**Request Body:**
```json
{
  "username": "admin",
  "password": "admin"
}
```

**Response 200 OK:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

**Response 400 Bad Request:**
```json
{
  "error": "Username and password are required"
}
```

**Response 401 Unauthorized:**
```json
{
  "error": "Invalid credentials"
}
```

**Пример использования:**
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
```

---

#### GET `/api/auth/credentials`

Получить имя администратора (без пароля).

**Аутентификация:** Требуется (Bearer Token)

**Response 200 OK:**
```json
{
  "username": "admin"
}
```

**Пример использования:**
```bash
curl -X GET http://localhost:5000/api/auth/credentials \
  -H "Authorization: Bearer $TOKEN"
```

---

#### POST `/api/auth/change-password`

Смена пароля администратора. После смены пароля все существующие токены становятся недействительными.

**Аутентификация:** Требуется (Bearer Token)

**Request Body:**
```json
{
  "old_password": "old_password",
  "new_password": "new_secure_password"
}
```

**Response 200 OK:**
```json
{
  "message": "Password changed successfully"
}
```

**Response 400 Bad Request:**
```json
{
  "error": "old_password and new_password are required"
}
```

**Response 401 Unauthorized:**
```json
{
  "error": "Invalid old password"
}
```

**Пример использования:**
```bash
curl -X POST http://localhost:5000/api/auth/change-password \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "old_password": "admin",
    "new_password": "newpassword"
  }'
```

---

#### POST `/api/auth/change-credentials`

Изменить имя пользователя и/или пароль администратора. После изменения все существующие токены становятся недействительными.

**Аутентификация:** Требуется (Bearer Token)

**Request Body:**
```json
{
  "old_password": "old_password",
  "new_username": "newadmin",
  "new_password": "new_secure_password"
}
```

**Поля запроса:**
- `old_password` (string, обязателен при смене пароля): Текущий пароль
- `new_username` (string, опционально): Новое имя пользователя
- `new_password` (string, обязателен при смене пароля): Новый пароль

**Response 200 OK:**
```json
{
  "message": "Credentials changed successfully"
}
```

**Response 400 Bad Request:**
```json
{
  "error": "old_password and new_password are required"
}
```
или
```json
{
  "error": "new_username is required and cannot be empty"
}
```

**Response 401 Unauthorized:**
```json
{
  "error": "Invalid old password"
}
```

**Пример использования:**
```bash
# Изменить только пароль
curl -X POST http://localhost:5000/api/auth/change-credentials \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "old_password": "admin",
    "new_password": "newpassword"
  }'

# Изменить имя пользователя и пароль
curl -X POST http://localhost:5000/api/auth/change-credentials \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "old_password": "admin",
    "new_username": "newadmin",
    "new_password": "newpassword"
  }'
```

---

#### GET `/api/auth/status`

Проверка статуса аутентификации (включена ли авторизация).

**Аутентификация:** Не требуется

**Response 200 OK:**
```json
{
  "enabled": true
}
```

---

### ⚙️ Конфигурация сервера

#### GET `/api/config`

Получить текущую конфигурацию сервера (read-only).

**Аутентификация:** Требуется (Bearer Token)

**Response 200 OK:**
```json
{
  "external_ip": "203.0.113.1",
  "external_port": 57159,
  "server_public_key": "3F8x7K9vL2mN5pQ8rT1wY4zA6bC9dE0fG3hI=",
  "subnet": "10.6.13.0/24",
  "server_ip": "10.6.13.1",
  "enabled": true,
  "obfuscation": true,
  "obfuscation_key": "my-obfuscation-key-123",
  "obfuscator_verbosity": "INFO",
  "masking_type": "NONE",
  "masking_forced": false
}
```

**Поля ответа:**
- `external_ip` (string): Внешний IP адрес сервера
- `external_port` (integer): Порт WireGuard для подключения клиентов
- `server_public_key` (string): Публичный ключ сервера WireGuard
- `subnet` (string): Подсеть VPN в формате CIDR (например, "10.6.13.0/24"). Подсеть внутри VPN сети. Есть смысл изменять только в случае, если текущий диапазон адресов пересекается с уже используемым у клиентов. Всегда должен иметь маску /24.
- `server_ip` (string): IP адрес сервера в VPN подсети
- `enabled` (boolean): Включен ли WireGuard сервер и обфускатор. Если `false`, сервисы не запускаются.
- `obfuscation` (boolean): Включена ли обфускация трафика. Если выключить, сервер будет работать в режиме обычного WireGuard.
- `obfuscation_key` (string): Ключ обфускации, используемый для связи между WireGuard и обфускатором. Может быть любой ASCII строкой длиной до 300 символов.
- `obfuscator_verbosity` (string): Уровень детализации логов обфускатора (`ERROR`, `WARNING`, `INFO`, `DEBUG`, `TRACE`). В случае проблем могут помочь разобраться более детализированные логи.
- `masking_type` (string): Маскинг по умолчанию (`NONE`, `STUN`, `AUTO`). Тип маскинга, который будет у пользователей в конфигах по умолчанию. Протокол, под который будет маскироваться сетевой трафик. Используется для обхода блокировок.
- `masking_forced` (boolean): Не допускать другой маскинг. Не позволять подключаться пользователям с другим типом маскинга.

**Пример использования:**
```bash
curl -X GET http://localhost:5000/api/config \
  -H "Authorization: Bearer $TOKEN"
```

---

#### PATCH `/api/config`

Обновить параметры конфигурации сервера. Все изменения применяются автоматически (перегенерируются конфиги, перезапускаются сервисы).

**Аутентификация:** Требуется (Bearer Token)

**Request Body (все поля опциональны):**
```json
{
  "subnet": "10.6.14.0/24",
  "enabled": true,
  "obfuscation": true,
  "obfuscation_key": "new-obfuscation-key-456",
  "verbosity_level": "DEBUG",
  "masking_type": "STUN",
  "masking_forced": false
}
```

**Поля запроса:**
- `subnet` (string, опционально): Новая подсеть в формате `X.Y.Z.0/24`. Подсеть внутри VPN сети. Есть смысл изменять только в случае, если текущий диапазон адресов пересекается с уже используемым у клиентов. Всегда должен иметь маску /24.
- `enabled` (boolean, опционально): Включить/выключить WireGuard сервер и обфускатор. Если `false`, сервисы не запускаются.
- `obfuscation` (boolean, опционально): Включить/выключить обфускацию. Если выключить, сервер будет работать в режиме обычного WireGuard.
- `obfuscation_key` (string, опционально): Ключ обфускации (ASCII, до 300 символов). При изменении клиентам потребуется обновить конфигурации обфускатора.
- `verbosity_level` или `obfuscator_verbosity` (string, опционально): Уровень детализации логов обфускатора (`ERROR`, `WARNING`, `INFO`, `DEBUG`, `TRACE`). В случае проблем могут помочь разобраться более детализированные логи.
- `masking_type` (string, опционально): Маскинг по умолчанию (`NONE`, `STUN`, `AUTO`). Тип маскинга, который будет у пользователей в конфигах по умолчанию. Протокол, под который будет маскироваться сетевой трафик. Используется для обхода блокировок.
- `masking_forced` (boolean, опционально): Не допускать другой маскинг. Не позволять подключаться пользователям с другим типом маскинга.

**Response 200 OK:**
```json
{
  "external_ip": "203.0.113.1",
  "external_port": 57159,
  "server_public_key": "3F8x7K9vL2mN5pQ8rT1wY4zA6bC9dE0fG3hI=",
  "subnet": "10.6.14.0/24",
  "server_ip": "10.6.14.1",
  "enabled": true,
  "obfuscation": true,
  "obfuscation_key": "new-obfuscation-key-456",
  "obfuscator_verbosity": "DEBUG",
  "masking_type": "STUN",
  "masking_forced": false
}
```

**Response 400 Bad Request:**
```json
{
  "error": "subnet must be in format X.Y.Z.0/24"
}
```

**Пример использования:**
```bash
curl -X PATCH http://localhost:5000/api/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "obfuscation": true,
    "masking_type": "STUN",
    "obfuscator_verbosity": "DEBUG"
  }'
```

---

#### POST `/api/config/regenerate-keys`

Регенерировать ключевую пару сервера (приватный и публичный ключи). Все клиенты потребуется обновить, так как изменится публичный ключ сервера.

**Аутентификация:** Требуется (Bearer Token)

**Response 200 OK:**
```json
{
  "server_public_key": "nEwP7bK9vL2mN5pQ8rT1wY4zA6bC9dE0fG3hI="
}
```

**Пример использования:**
```bash
curl -X POST http://localhost:5000/api/config/regenerate-keys \
  -H "Authorization: Bearer $TOKEN"
```

---

### 👥 Управление клиентами

#### GET `/api/clients`

Получить список всех клиентов.

**Аутентификация:** Требуется (Bearer Token)

**Response 200 OK:**
```json
{
  "client1": {
    "username": "client1",
    "ip": 2,
    "ip_full": "10.6.13.2",
    "public_key": "abc123...",
    "private_key": "def456...",
    "allowed_ips": ["0.0.0.0/0", "::/0"],
    "obfuscator_port": 13255,
    "masking_type_override": null,
    "enabled": true,
    "is_connected": true,
    "latest_handshake": 1704067200
  },
  "client2": {
    "username": "client2",
    "ip": 3,
    "ip_full": "10.6.13.3",
    "public_key": "xyz789...",
    "private_key": "uvw012...",
    "allowed_ips": ["0.0.0.0/0"],
    "obfuscator_port": 13256,
    "masking_type_override": "STUN",
    "enabled": true,
    "is_connected": false,
    "latest_handshake": 0
  }
}
```

**Поля объекта клиента:**
- `username` (string): Имя пользователя (ключ объекта)
- `ip` (integer): Последний октет IP адреса клиента в VPN подсети
- `ip_full` (string): Полный IP адрес клиента в VPN подсети (например, "10.6.13.2")
- `public_key` (string): Публичный ключ WireGuard клиента
- `private_key` (string): Приватный ключ WireGuard клиента (хранится на сервере)
- `allowed_ips` (array[string]): Разрешенные IP адреса/подсети для маршрутизации в формате CIDR (например, "0.0.0.0/0"). Список IP адресов и подсетей, пакеты для которых будут направляться через VPN соединение. Формат: адрес/маска (например, 0.0.0.0/0 для всего интернет-трафика). Необходимо указать хотя бы одну подсеть.
- `obfuscator_port` (integer, опционально): Порт обфускатора для данного клиента (1-65535). Порт, который будет использоваться для взаимодействия между WireGuard и WireGuard Obfuscator на устройстве пользователя. Может быть любым свободным портом от 1 до 65535. Рекомендуется изменять только в случае, если используемый порт уже занят другим приложением.
- `masking_type_override` (string|null, опционально): Переопределение типа маскировки для клиента (`NONE`, `STUN`, `AUTO` или `null` для использования значения по умолчанию). Протокол, под который будет маскироваться сетевой трафик. Используется для обхода блокировок. Доступно только если `masking_forced` в конфигурации сервера установлен в `false`.
- `enabled` (boolean): Включен ли клиент (по умолчанию `true`). Если `false`, клиент исключается из конфигурации WireGuard
- `is_connected` (boolean): Подключен ли клиент в данный момент (handshake был менее 180 секунд назад)
- `latest_handshake` (integer): UNIX timestamp последнего успешного handshake (0, если никогда не было). Значение сохраняется в базе данных и используется, если статистика WireGuard недоступна.

**Пример использования:**
```bash
curl -X GET http://localhost:5000/api/clients \
  -H "Authorization: Bearer $TOKEN"
```

---

#### GET `/api/clients/<username>`

Получить информацию о конкретном клиенте.

**Аутентификация:** Требуется (Bearer Token)

**URL Параметры:**
- `username` (string, required): Имя клиента

**Response 200 OK:**
```json
{
  "username": "client1",
  "ip": 2,
  "ip_full": "10.6.13.2",
  "public_key": "abc123...",
  "private_key": "def456...",
  "allowed_ips": ["0.0.0.0/0", "::/0"],
  "obfuscator_port": 13255,
  "masking_type_override": null,
  "enabled": true,
  "is_connected": true,
  "latest_handshake": 1704067200
}
```

**Response 404 Not Found:**
```json
{
  "error": "Client not found"
}
```

**Пример использования:**
```bash
curl -X GET http://localhost:5000/api/clients/client1 \
  -H "Authorization: Bearer $TOKEN"
```

---

#### POST `/api/clients`

Создать нового клиента. Автоматически генерируются ключи, назначается IP адрес, применяются изменения конфигурации.

**Аутентификация:** Требуется (Bearer Token)

**Request Body:**
```json
{
  "username": "newclient",
  "enabled": true
}
```

**Поля запроса:**
- `username` (string, required): Имя нового клиента
- `enabled` (boolean, опционально): Включить ли клиента при создании (по умолчанию `true`)

**Response 201 Created:**
```json
{
  "username": "newclient",
  "ip": 4,
  "ip_full": "10.6.13.4",
  "public_key": "new123...",
  "private_key": "new456...",
  "allowed_ips": ["0.0.0.0/0"],
  "obfuscator_port": 13255,
  "masking_type_override": null,
  "enabled": true,
  "is_connected": false,
  "latest_handshake": 0
}
```

**Response 400 Bad Request:**
```json
{
  "error": "username is required"
}
```

или

```json
{
  "error": "Client already exists"
}
```

**Пример использования:**
```bash
curl -X POST http://localhost:5000/api/clients \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newclient",
    "obfuscation": true
  }'
```

---

#### PATCH `/api/clients/<username>`

Обновить конфигурацию клиента. Все изменения применяются автоматически.

**Аутентификация:** Требуется (Bearer Token)

**URL Параметры:**
- `username` (string, required): Имя клиента

**Request Body (все поля опциональны):**
```json
{
  "allowed_ips": ["0.0.0.0/0", "::/0"],
  "obfuscator_port": 13255,
  "masking_type_override": "STUN",
  "enabled": true
}
```

**Поля запроса:**
- `allowed_ips` (array[string], опционально): Разрешенные IP адреса/подсети в формате CIDR (например, "0.0.0.0/0"). Список IP адресов и подсетей, пакеты для которых будут направляться через VPN соединение. Формат: адрес/маска (например, 0.0.0.0/0 для всего интернет-трафика). Необходимо указать хотя бы одну подсеть.
- `obfuscator_port` (integer, опционально): Порт обфускатора (1-65535). Порт, который будет использоваться для взаимодействия между WireGuard и WireGuard Obfuscator на устройстве пользователя. Может быть любым свободным портом от 1 до 65535. Рекомендуется изменять только в случае, если используемый порт уже занят другим приложением.
- `masking_type_override` (string|null, опционально): Переопределение типа маскировки (`NONE`, `STUN`, `AUTO` или `null` для удаления переопределения). Протокол, под который будет маскироваться сетевой трафик. Используется для обхода блокировок. Доступно только если `masking_forced` в конфигурации сервера установлен в `false`.
- `enabled` (boolean, опционально): Включить/выключить клиента

**Response 200 OK:**
```json
{
  "username": "client1",
  "ip": 2,
  "ip_full": "10.6.13.2",
  "public_key": "abc123...",
  "private_key": "def456...",
  "allowed_ips": ["0.0.0.0/0", "::/0"],
  "obfuscator_port": 13255,
  "masking_type_override": "STUN",
  "enabled": true,
  "is_connected": true,
  "latest_handshake": 1704067200
}
```

**Response 400 Bad Request:**
```json
{
  "error": "allowed_ips must be a list of strings"
}
```

или

```json
{
  "error": "masking_type_override cannot be set when masking_forced is true"
}
```

или

```json
{
  "error": "obfuscator_port must be between 1 and 65535"
}
```

или

```json
{
  "error": "Invalid CIDR format in allowed_ips"
}
```

или

```json
{
  "error": "allowed_ips must contain at least one subnet"
}
```

**Response 404 Not Found:**
```json
{
  "error": "Client not found"
}
```

**Пример использования:**
```bash
curl -X PATCH http://localhost:5000/api/clients/client1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "allowed_ips": ["10.0.0.0/8", "192.168.0.0/16"],
    "enabled": true
  }'
```

---

#### DELETE `/api/clients/<username>`

Удалить клиента. Клиент полностью удаляется из конфигурации, изменения применяются автоматически.

**Аутентификация:** Требуется (Bearer Token)

**URL Параметры:**
- `username` (string, required): Имя клиента

**Response 200 OK:**
```json
{
  "message": "Client client1 deleted successfully"
}
```

**Response 404 Not Found:**
```json
{
  "error": "Client not found"
}
```

**Пример использования:**
```bash
curl -X DELETE http://localhost:5000/api/clients/client1 \
  -H "Authorization: Bearer $TOKEN"
```

---

#### POST `/api/clients/<username>/regenerate-keys`

Регенерировать ключевую пару клиента. После регенерации клиенту потребуется обновить конфигурацию.

**Аутентификация:** Требуется (Bearer Token)

**URL Параметры:**
- `username` (string, required): Имя клиента

**Response 200 OK:**
```json
{
  "private_key": "new_private_key...",
  "public_key": "new_public_key..."
}
```

**Response 404 Not Found:**
```json
{
  "error": "Client not found"
}
```

**Пример использования:**
```bash
curl -X POST http://localhost:5000/api/clients/client1/regenerate-keys \
  -H "Authorization: Bearer $TOKEN"
```

---

#### GET `/api/clients/<username>/config/wireguard`

Получить WireGuard конфигурацию для клиента в формате текстового файла для скачивания.

**Аутентификация:** Требуется (Bearer Token)

**URL Параметры:**
- `username` (string, required): Имя клиента

**Response 200 OK:**
```
[Interface]
PrivateKey = client_private_key_here
Address = 10.6.13.2/32
DNS = 1.1.1.1, 8.8.8.8

[Peer]
PublicKey = server_public_key_here
Endpoint = 203.0.113.1:57159
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
```

**Content-Type:** `text/plain`

**Headers:**
- `Content-Disposition: attachment; filename="<username>-wireguard.conf"`

**Response 404 Not Found:**
```json
{
  "error": "Client not found"
}
```

**Пример использования:**
```bash
curl -X GET http://localhost:5000/api/clients/client1/config/wireguard \
  -H "Authorization: Bearer $TOKEN" \
  -o client1-wireguard.conf
```

---

#### GET `/api/clients/<username>/config/obfuscator`

Получить конфигурацию обфускатора для клиента в формате текстового файла для скачивания.

**Аутентификация:** Требуется (Bearer Token)

**URL Параметры:**
- `username` (string, required): Имя клиента

**Response 200 OK:**
```
[Interface]
PrivateKey = client_private_key_here
Address = 10.6.13.2/32
DNS = 1.1.1.1, 8.8.8.8

[Peer]
PublicKey = server_public_key_here
Endpoint = 127.0.0.1:13255
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
```

**Content-Type:** `text/plain`

**Headers:**
- `Content-Disposition: attachment; filename="<username>-obfuscator.conf"`

**Response 400 Bad Request:**
```json
{
  "error": "Obfuscation is disabled"
}
```

**Response 404 Not Found:**
```json
{
  "error": "Client not found"
}
```

**Пример использования:**
```bash
curl -X GET http://localhost:5000/api/clients/client1/config/obfuscator \
  -H "Authorization: Bearer $TOKEN" \
  -o client1-obfuscator.conf
```

---

### 📊 Статистика и мониторинг

#### GET `/api/status`

Получить общий статус сервера, включая статус WireGuard и обфускатора, количество клиентов и подключенных клиентов.

**Аутентификация:** Требуется (Bearer Token)

**Response 200 OK:**
```json
{
  "external_ip": "203.0.113.1",
  "external_port": 57159,
  "subnet": "10.6.13.0/24",
  "server_ip": "10.6.13.1",
  "server_public_key": "3F8x7K9vL2mN5pQ8rT1wY4zA6bC9dE0fG3hI=",
  "clients_count": 5,
  "connected_clients_count": 3,
  "wireguard": {
    "running": true,
    "error": null
  },
  "obfuscator": {
    "enabled": true,
    "running": true,
    "error": null,
    "exit_code": null,
    "version": "1.2.3"
  }
}
```

**Поля ответа:**
- `external_ip` (string): Внешний IP адрес сервера
- `external_port` (integer): Порт WireGuard
- `subnet` (string): VPN подсеть в формате CIDR
- `server_ip` (string): IP адрес сервера в VPN подсети
- `server_public_key` (string): Публичный ключ сервера
- `clients_count` (integer): Общее количество клиентов
- `connected_clients_count` (integer): Количество подключенных клиентов (handshake < 180 секунд)
- `wireguard.running` (boolean): Запущен ли WireGuard интерфейс
- `wireguard.error` (string|null): Ошибка WireGuard, если есть
- `obfuscator.enabled` (boolean): Включена ли обфускация в конфигурации
- `obfuscator.running` (boolean): Запущен ли процесс обфускатора
- `obfuscator.error` (string|null): Ошибка обфускатора, если есть
- `obfuscator.exit_code` (integer|null): Код выхода процесса обфускатора, если завершился
- `obfuscator.version` (string|null): Версия wg-obfuscator

**Пример использования:**
```bash
curl -X GET http://localhost:5000/api/status \
  -H "Authorization: Bearer $TOKEN"
```

---

#### GET `/api/stats`

Получить статистику WireGuard для всех пиров (клиентов), включая информацию о передаче данных и состоянии подключений.

**Аутентификация:** Требуется (Bearer Token)

**Response 200 OK:**
```json
{
  "interface": "wg0",
  "peers": [
    {
      "public_key": "abc123...",
      "client_name": "client1",
      "endpoint": "203.0.113.50:54321",
      "allowed_ips": "10.6.13.2/32",
      "latest_handshake": 1704067200,
      "transfer_rx_bytes": 1048576,
      "transfer_tx_bytes": 524288,
      "is_connected": true
    },
    {
      "public_key": "xyz789...",
      "client_name": "client2",
      "endpoint": null,
      "allowed_ips": "10.6.13.3/32",
      "latest_handshake": 0,
      "transfer_rx_bytes": 0,
      "transfer_tx_bytes": 0,
      "is_connected": false
    }
  ]
}
```

**Поля ответа:**
- `interface` (string): Имя интерфейса WireGuard (обычно `wg0`)
- `peers` (array): Массив объектов с информацией о пирах
  - `public_key` (string): Публичный ключ пира
  - `client_name` (string|null): Имя клиента, если найдено в конфигурации
  - `endpoint` (string|null): IP:порт удаленного пира, если подключен
  - `allowed_ips` (string): Разрешенные IP адреса для этого пира
  - `latest_handshake` (integer): UNIX timestamp последнего handshake (0, если никогда не было)
  - `transfer_rx_bytes` (integer): Всего получено байт (cumulative)
  - `transfer_tx_bytes` (integer): Всего отправлено байт (cumulative)
  - `is_connected` (boolean): Подключен ли пир (handshake < 180 секунд назад)

**Response 503 Service Unavailable:**
```json
{
  "error": "WireGuard interface not found or not running"
}
```

**Пример использования:**
```bash
curl -X GET http://localhost:5000/api/stats \
  -H "Authorization: Bearer $TOKEN"
```

---

#### GET `/api/stats/<username>`

Получить статистику WireGuard для конкретного клиента.

**Аутентификация:** Требуется (Bearer Token)

**URL Параметры:**
- `username` (string, required): Имя клиента

**Response 200 OK (если клиент подключен):**
```json
{
  "public_key": "abc123...",
  "client_name": "client1",
  "endpoint": "203.0.113.50:54321",
  "allowed_ips": "10.6.13.2/32",
  "latest_handshake": 1704067200,
  "transfer_rx_bytes": 1048576,
  "transfer_tx_bytes": 524288,
  "is_connected": true
}
```

**Response 200 OK (если клиент не подключен):**
```json
{
  "public_key": "abc123...",
  "client_name": "client1",
  "is_connected": false,
  "message": "Client not currently connected"
}
```

**Response 404 Not Found:**
```json
{
  "error": "Client not found"
}
```

**Response 503 Service Unavailable:**
```json
{
  "error": "WireGuard interface not found or not running"
}
```

**Пример использования:**
```bash
curl -X GET http://localhost:5000/api/stats/client1 \
  -H "Authorization: Bearer $TOKEN"
```

---

#### GET `/api/logs/obfuscator`

Получить последние N строк логов обфускатора из памяти.

**Аутентификация:** Требуется (Bearer Token)

**Query Параметры:**
- `lines` (integer, опционально): Количество строк логов (по умолчанию 100, максимум 10000)

**Response 200 OK:**
```json
{
  "lines": [
    "2024-01-01T12:00:00Z [INFO] Starting obfuscator...",
    "2024-01-01T12:00:01Z [INFO] Obfuscator started successfully",
    "2024-01-01T12:00:05Z [DEBUG] Client connected: 10.6.13.2"
  ],
  "total_lines": 150,
  "requested_lines": 100,
  "returned_lines": 100
}
```

**Поля ответа:**
- `lines` (array[string]): Массив строк логов
- `total_lines` (integer): Всего строк в логах
- `requested_lines` (integer): Запрошенное количество строк
- `returned_lines` (integer): Возвращено строк

**Response 400 Bad Request:**
```json
{
  "error": "lines parameter must be between 1 and 10000"
}
```

**Пример использования:**
```bash
curl -X GET "http://localhost:5000/api/logs/obfuscator?lines=50" \
  -H "Authorization: Bearer $TOKEN"
```

---

### 📊 Grafana Integration Endpoints

Endpoints для интеграции с Grafana через JSON API data source. Все endpoints возвращают данные в формате, совместимом с Grafana JSON API.

#### GET `/api/grafana/clients/<username>/traffic`

Получить статистику трафика клиента в формате Grafana (скорость в байтах/сек).

**Аутентификация:** Требуется (Bearer Token)

**URL Параметры:**
- `username` (string, required): Имя клиента

**Query Параметры:**
- `from` (integer, опционально): Начальное время (Unix timestamp в секундах или миллисекундах)
- `to` (integer, опционально): Конечное время (Unix timestamp в секундах или миллисекундах)
- `interval` (integer, опционально): Интервал агрегации в секундах

**Response 200 OK:**
```json
[
  {
    "target": "client1 - Received",
    "datapoints": [
      [1024000, 1704110400000],
      [2048000, 1704110405000],
      [1536000, 1704110410000]
    ]
  },
  {
    "target": "client1 - Sent",
    "datapoints": [
      [51200, 1704110400000],
      [61440, 1704110405000],
      [40960, 1704110410000]
    ]
  }
]
```

**Формат:**
- `target`: Название серии данных
- `datapoints`: Массив `[значение, timestamp_в_миллисекундах]`
- Значения представляют скорость в байтах в секунду

**Пример использования:**
```bash
curl -X GET "http://localhost:5000/api/grafana/clients/client1/traffic?from=1704110400&to=1704114000" \
  -H "Authorization: Bearer $TOKEN"
```

---

#### GET `/api/grafana/clients/<username>/traffic-bytes`

Получить статистику трафика клиента в формате Grafana (общее количество байт за интервал).

**Аутентификация:** Требуется (Bearer Token)

**URL Параметры:**
- `username` (string, required): Имя клиента

**Query Параметры:**
- `from` (integer, опционально): Начальное время (Unix timestamp в секундах или миллисекундах)
- `to` (integer, опционально): Конечное время (Unix timestamp в секундах или миллисекундах)
- `interval` (integer, опционально): Интервал агрегации в секундах

**Response 200 OK:**
```json
[
  {
    "target": "client1 - Received Bytes",
    "datapoints": [
      [5120000, 1704110400000],
      [10240000, 1704110405000],
      [7680000, 1704110410000]
    ]
  },
  {
    "target": "client1 - Sent Bytes",
    "datapoints": [
      [256000, 1704110400000],
      [307200, 1704110405000],
      [204800, 1704110410000]
    ]
  }
]
```

**Формат:**
- Значения представляют общее количество байт за интервал времени

**Пример использования:**
```bash
curl -X GET "http://localhost:5000/api/grafana/clients/client1/traffic-bytes?from=1704110400&to=1704114000" \
  -H "Authorization: Bearer $TOKEN"
```

---

#### GET `/api/grafana/clients`

Получить список всех клиентов для использования в Grafana query builder.

**Аутентификация:** Требуется (Bearer Token)

**Response 200 OK:**
```json
[
  {"text": "client1", "value": "client1"},
  {"text": "client2", "value": "client2"},
  {"text": "client3", "value": "client3"}
]
```

**Пример использования:**
```bash
curl -X GET http://localhost:5000/api/grafana/clients \
  -H "Authorization: Bearer $TOKEN"
```

---

#### GET `/api/grafana/status`

Получить метрики состояния сервера для Grafana.

**Аутентификация:** Требуется (Bearer Token)

**Response 200 OK:**
```json
[
  {
    "target": "Total Clients",
    "datapoints": [[5, 1704110400000]]
  },
  {
    "target": "Connected Clients",
    "datapoints": [[3, 1704110400000]]
  },
  {
    "target": "WireGuard Running",
    "datapoints": [[1, 1704110400000]]
  },
  {
    "target": "Obfuscator Enabled",
    "datapoints": [[1, 1704110400000]]
  },
  {
    "target": "Obfuscator Running",
    "datapoints": [[1, 1704110400000]]
  }
]
```

**Метрики:**
- `Total Clients`: Общее количество клиентов
- `Connected Clients`: Количество подключенных клиентов
- `WireGuard Running`: 1 если WireGuard запущен, 0 если нет
- `Obfuscator Enabled`: 1 если обфускация включена, 0 если нет
- `Obfuscator Running`: 1 если обфускатор запущен, 0 если нет

**Пример использования:**
```bash
curl -X GET http://localhost:5000/api/grafana/status \
  -H "Authorization: Bearer $TOKEN"
```

**Настройка в Grafana:**

1. Добавить новый Data Source типа "JSON API"
2. Указать URL: `http://your-server:5000/api/grafana`
3. Настроить аутентификацию:
   - В "HTTP" → "Headers" добавить: `Authorization: Bearer YOUR_TOKEN`
4. Для запроса трафика использовать endpoint: `/clients/{username}/traffic`
   - В Grafana Query использовать: `?from=${__from}&to=${__to}`

---

### 🏥 Health Check

#### GET `/health`

Проверка работоспособности сервиса. Используется для мониторинга и проверки доступности API.

**Аутентификация:** Не требуется

**Response 200 OK:**
```json
{
  "status": "ok"
}
```

**Пример использования:**
```bash
curl -X GET http://localhost:5000/health
```

---

## Примеры использования

### Полный цикл: создание клиента и получение конфигурации

```bash
# 1. Авторизация
TOKEN=$(curl -s -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}' \
  | jq -r '.access_token')

# 2. Создание клиента
curl -X POST http://localhost:5000/api/clients \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username": "myclient", "enabled": true}'

# 3. Получение конфигурации WireGuard
curl -X GET http://localhost:5000/api/clients/myclient/config/wireguard \
  -H "Authorization: Bearer $TOKEN" \
  -o myclient-wireguard.conf

# 4. Получение конфигурации обфускатора (если включена обфускация)
curl -X GET http://localhost:5000/api/clients/myclient/config/obfuscator \
  -H "Authorization: Bearer $TOKEN" \
  -o myclient-obfuscator.conf
```

### Обновление конфигурации сервера

```bash
curl -X PATCH http://localhost:5000/api/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "obfuscation": true,
    "masking_type": "STUN",
    "obfuscator_verbosity": "DEBUG"
  }'
```

### Управление клиентом

```bash
# Получить информацию о клиенте
curl -X GET http://localhost:5000/api/clients/myclient \
  -H "Authorization: Bearer $TOKEN"

# Обновить настройки клиента
curl -X PATCH http://localhost:5000/api/clients/myclient \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "allowed_ips": ["10.0.0.0/8"],
    "enabled": true
  }'

# Выключить клиента
curl -X PATCH http://localhost:5000/api/clients/myclient \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'

# Регенерировать ключи клиента
curl -X POST http://localhost:5000/api/clients/myclient/regenerate-keys \
  -H "Authorization: Bearer $TOKEN"

# Удалить клиента
curl -X DELETE http://localhost:5000/api/clients/myclient \
  -H "Authorization: Bearer $TOKEN"
```

### Мониторинг и статистика

```bash
# Получить статус сервера
curl -X GET http://localhost:5000/api/status \
  -H "Authorization: Bearer $TOKEN"

# Получить статистику всех клиентов
curl -X GET http://localhost:5000/api/stats \
  -H "Authorization: Bearer $TOKEN"

# Получить статистику конкретного клиента
curl -X GET http://localhost:5000/api/stats/myclient \
  -H "Authorization: Bearer $TOKEN"

# Получить логи обфускатора
curl -X GET "http://localhost:5000/api/logs/obfuscator?lines=100" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Коды ошибок

API использует стандартные HTTP коды статуса:

- **200 OK**: Успешный запрос
- **201 Created**: Ресурс успешно создан
- **400 Bad Request**: Неверный формат запроса или валидация не прошла
- **401 Unauthorized**: Требуется аутентификация или неверный токен
- **404 Not Found**: Ресурс не найден (клиент, endpoint)
- **500 Internal Server Error**: Внутренняя ошибка сервера
- **503 Service Unavailable**: Сервис недоступен (например, WireGuard не запущен)

Все ошибки возвращаются в формате:

```json
{
  "error": "Описание ошибки"
}
```

---

## Разработка

### Структура модулей

- **config**: Управление конфигурацией через `ConfigManager`
- **auth**: Аутентификация через токены с `TokenManager`
- **wireguard**: Генерация конфигов и управление WireGuard
- **obfuscator**: Управление процессом обфускатора и логированием
- **clients**: Бизнес-логика работы с клиентами
- **api**: Flask Blueprints для всех эндпоинтов
- **services**: Оркестрация применения изменений

### Логирование

Логирование настроено через стандартный модуль `logging` Python. Логи выводятся только в stdout/stderr, что удобно для Docker, который автоматически собирает логи из контейнера.

Уровни логирования:
- `INFO`: Общая информация о работе
- `DEBUG`: Детальная отладочная информация
- `WARNING`: Предупреждения
- `ERROR`: Ошибки

### Обработка ошибок

Используются кастомные исключения из `app.exceptions`:
- `WireGuardError`: Базовое исключение
- `ClientNotFoundError`: Клиент не найден
- `ConfigValidationError`: Ошибка валидации конфигурации
- `ServiceError`: Ошибка работы сервисов

---

## Лицензия

Copyright (C) 2025 Alexey Cluster <cluster@cluster.wtf>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
