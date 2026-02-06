# Deployment Guide

A step-by-step guide to deploy AI Hub on any Linux server (VPS, cloud instance, or bare metal).

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Server Preparation](#server-preparation)
3. [Application Setup](#application-setup)
4. [Reverse Proxy](#reverse-proxy)
5. [SSL/HTTPS](#sslhttps)
6. [Process Management](#process-management)
7. [Firewall](#firewall)
8. [Monitoring](#monitoring)
9. [Backups](#backups)
10. [Maintenance](#maintenance)

---

## Prerequisites

### Server Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 1 vCPU | 2+ vCPUs |
| RAM | 1 GB | 2-4 GB |
| Disk | 5 GB | 10+ GB SSD |
| OS | Ubuntu 22.04+ / Debian 12+ | Latest LTS |

### Required Software

- Python 3.13+
- Claude Code CLI (authenticated)
- nginx (reverse proxy)
- certbot (SSL)

### Network

- Domain name pointing to server IP (for HTTPS)
- Ports 80, 443 open for web traffic
- Port 22 for SSH (restrict to your IP if possible)

---

## Server Preparation

### 1. Create a Dedicated User

Never run the application as root.

```bash
# Create user
sudo useradd -m -s /bin/bash aihub

# Add to sudo group (optional, for maintenance)
sudo usermod -aG sudo aihub

# Switch to user
sudo -u aihub -i
```

### 2. Install System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y \
    git \
    curl \
    nginx \
    certbot \
    python3-certbot-nginx \
    ffmpeg  # Only if using voice features
```

### 3. Install uv (Python Package Manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

### 4. Install Claude Code CLI

```bash
# Install Node.js if not present
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Install Claude Code
npm install -g @anthropic-ai/claude-code

# Authenticate (follow prompts)
claude auth
```

---

## Application Setup

### 1. Clone Repository

```bash
cd /home/aihub
git clone https://github.com/jesusroncal94/ai-hub.git
cd ai-hub
```

### 2. Install Dependencies

```bash
# Without voice support
uv sync

# With voice support (adds ~7GB)
uv sync --extra voice
```

### 3. Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit configuration
nano .env
```

**Critical settings for production:**

```bash
# REQUIRED: Set a strong admin password
AI_HUB_ADMIN_PASSWORD=your-very-secure-password-here

# Keep localhost (nginx will proxy)
AI_HUB_HOST=127.0.0.1
AI_HUB_PORT=7860

# Adjust as needed
AI_HUB_MAX_UPLOAD_MB=50
```

### 4. Set Permissions

```bash
# Secure data directory
mkdir -p .data
chmod 700 .data

# Secure env file
chmod 600 .env
```

### 5. Test Application

```bash
# Run manually to verify
uv run ai-hub

# Check it's accessible locally
curl http://127.0.0.1:7860
```

---

## Reverse Proxy

Using nginx as a reverse proxy provides:
- HTTPS termination
- Rate limiting
- Security headers
- Static file caching

### 1. Create nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/ai-hub
```

```nginx
# Rate limiting zone
limit_req_zone $binary_remote_addr zone=ai_hub_limit:10m rate=10r/s;

server {
    listen 80;
    server_name your-domain.com;

    # Redirect HTTP to HTTPS (after certbot setup)
    # return 301 https://$server_name$request_uri;

    location / {
        proxy_pass http://127.0.0.1:7860;
        proxy_http_version 1.1;

        # WebSocket support (required for Gradio)
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Forward client info
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts for long AI responses
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;

        # Rate limiting
        limit_req zone=ai_hub_limit burst=20 nodelay;
    }

    # Upload size limit
    client_max_body_size 50M;
}
```

### 2. Enable Site

```bash
sudo ln -s /etc/nginx/sites-available/ai-hub /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## SSL/HTTPS

### Option A: Let's Encrypt (Free)

```bash
sudo certbot --nginx -d your-domain.com
```

Certbot will:
- Obtain certificate
- Configure nginx
- Set up auto-renewal

### Option B: Custom Certificate

```bash
# Copy certificates
sudo cp your-cert.crt /etc/ssl/certs/ai-hub.crt
sudo cp your-cert.key /etc/ssl/private/ai-hub.key

# Update nginx config manually
```

### Security Headers

Add to nginx server block:

```nginx
# Security headers
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

---

## Process Management

### Using systemd

Create service file:

```bash
sudo nano /etc/systemd/system/ai-hub.service
```

```ini
[Unit]
Description=AI Hub - Claude Code Chat Interface
After=network.target

[Service]
Type=simple
User=aihub
Group=aihub
WorkingDirectory=/home/aihub/ai-hub
EnvironmentFile=/home/aihub/ai-hub/.env
ExecStart=/home/aihub/.local/bin/uv run ai-hub
Restart=always
RestartSec=10

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/aihub/ai-hub/.data

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ai-hub
sudo systemctl start ai-hub

# Check status
sudo systemctl status ai-hub

# View logs
sudo journalctl -u ai-hub -f
```

---

## Firewall

### Using UFW (Uncomplicated Firewall)

```bash
# Reset to defaults
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (adjust port if changed)
sudo ufw allow ssh

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

### Optional: Restrict SSH by IP

```bash
# Allow SSH only from specific IP
sudo ufw allow from YOUR_IP to any port 22
```

---

## Monitoring

### Application Logs

```bash
# Audit log (security events)
tail -f /home/aihub/ai-hub/.data/audit.log

# Systemd service logs
sudo journalctl -u ai-hub -f

# Nginx access log
tail -f /var/log/nginx/access.log
```

### System Monitoring

```bash
# Install htop for resource monitoring
sudo apt install -y htop

# Check disk usage
df -h

# Check memory
free -h
```

### Optional: Fail2ban

Protect against brute force attacks:

```bash
sudo apt install -y fail2ban

# Create jail for nginx
sudo nano /etc/fail2ban/jail.local
```

```ini
[nginx-limit-req]
enabled = true
filter = nginx-limit-req
action = iptables-multiport[name=nginx, port="http,https"]
logpath = /var/log/nginx/error.log
findtime = 600
maxretry = 10
bantime = 3600
```

```bash
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

---

## Backups

### Automated Backup Script

```bash
nano /home/aihub/backup.sh
```

```bash
#!/bin/bash
# AI Hub Backup Script

BACKUP_DIR="/home/aihub/backups"
APP_DIR="/home/aihub/ai-hub"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="ai-hub-backup-${DATE}.tar.gz"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup data and config
tar -czf "${BACKUP_DIR}/${BACKUP_FILE}" \
    -C "$APP_DIR" \
    .data \
    .env

# Keep only last 7 backups
ls -t "${BACKUP_DIR}"/ai-hub-backup-*.tar.gz | tail -n +8 | xargs -r rm

echo "Backup created: ${BACKUP_FILE}"
```

```bash
chmod +x /home/aihub/backup.sh
```

### Schedule with Cron

```bash
crontab -e
```

```cron
# Daily backup at 2 AM
0 2 * * * /home/aihub/backup.sh >> /home/aihub/backup.log 2>&1
```

### Restore from Backup

```bash
# Stop service
sudo systemctl stop ai-hub

# Restore
cd /home/aihub/ai-hub
tar -xzf /home/aihub/backups/ai-hub-backup-YYYYMMDD_HHMMSS.tar.gz

# Start service
sudo systemctl start ai-hub
```

---

## Maintenance

### Update Application

```bash
# Stop service
sudo systemctl stop ai-hub

# Pull updates
cd /home/aihub/ai-hub
git pull

# Update dependencies
uv sync

# Start service
sudo systemctl start ai-hub
```

### Update System

```bash
# Regular security updates
sudo apt update && sudo apt upgrade -y

# Reboot if kernel updated
sudo reboot
```

### Renew SSL Certificate

Certbot auto-renews, but you can test:

```bash
sudo certbot renew --dry-run
```

### Log Rotation

Nginx logs rotate automatically. For audit logs:

```bash
sudo nano /etc/logrotate.d/ai-hub
```

```
/home/aihub/ai-hub/.data/audit.log {
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
    create 640 aihub aihub
}
```

---

## Troubleshooting

### Application Won't Start

```bash
# Check logs
sudo journalctl -u ai-hub -n 50

# Test manually
cd /home/aihub/ai-hub
uv run ai-hub
```

### 502 Bad Gateway

```bash
# Check if app is running
sudo systemctl status ai-hub

# Check if port is listening
ss -tlnp | grep 7860
```

### Permission Denied

```bash
# Fix ownership
sudo chown -R aihub:aihub /home/aihub/ai-hub

# Fix data directory
chmod 700 /home/aihub/ai-hub/.data
```

### High Memory Usage

```bash
# Check what's using memory
htop

# Restart service to free memory
sudo systemctl restart ai-hub
```

---

## Security Checklist

Before going live:

- [ ] Strong admin password in `.env`
- [ ] `.env` file has `chmod 600`
- [ ] `.data/` directory has `chmod 700`
- [ ] HTTPS enabled with valid certificate
- [ ] Firewall configured (UFW)
- [ ] SSH key-only authentication
- [ ] Fail2ban installed
- [ ] Automated backups configured
- [ ] Security updates enabled

---

[← Back to Documentation](README.md)
