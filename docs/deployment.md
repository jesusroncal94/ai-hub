# Deployment

## Resource Requirements

### Minimum (1-2 concurrent users, no voice)

| Resource | Specification |
|----------|---------------|
| **CPU** | 1 vCPU |
| **RAM** | 512 MB - 1 GB |
| **Disk** | 2 GB |
| **Network** | Stable internet connection |
| **OS** | Linux (Ubuntu 22.04+), macOS, Windows WSL |

### Recommended (5-10 concurrent users, no voice)

| Resource | Specification |
|----------|---------------|
| **CPU** | 2-4 vCPUs |
| **RAM** | 2-4 GB |
| **Disk** | 5 GB SSD |
| **Network** | 10+ Mbps |
| **OS** | Ubuntu 22.04+ LTS |

### With Voice (Whisper enabled)

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| **CPU** | 4 vCPUs | 8 vCPUs |
| **RAM** | 4 GB | 8-16 GB |
| **GPU** | - | NVIDIA 4+ GB VRAM |
| **Disk** | 10 GB | 15 GB SSD |

---

## Memory Breakdown

| Component | Idle | Active |
|-----------|------|--------|
| Python runtime | 50 MB | 50 MB |
| Gradio server | 150 MB | 300 MB |
| Per concurrent user | - | +50-100 MB |
| SQLite | 5 MB | 20 MB |
| Claude CLI (per request) | - | +50-100 MB |
| **Total (no voice)** | ~200 MB | ~500 MB + users |

### With Whisper

| Model | Additional RAM |
|-------|---------------|
| base | +500 MB |
| small | +1 GB |
| medium | +2.5 GB |

---

## Storage Requirements

| Component | Size |
|-----------|------|
| Base install (no voice) | ~500 MB |
| With voice (PyTorch + Whisper) | ~7 GB |
| Database (per message) | ~1 KB |
| Uploads | Variable |

---

## Scaling Guide

| Concurrent Users | RAM | CPUs |
|-----------------|-----|------|
| 1-5 | 2 GB | 2 |
| 5-15 | 4 GB | 4 |
| 15-30 | 8 GB | 4-8 |
| 30+ | Multiple instances | - |

---

## Production Setup

### 1. Basic Deployment

```bash
# Clone and install
git clone https://github.com/jesusroncal94/ai-hub.git
cd ai-hub
uv sync

# Run in background
nohup uv run ai-hub > ai-hub.log 2>&1 &
```

### 2. With systemd (Recommended)

Create `/etc/systemd/system/ai-hub.service`:

```ini
[Unit]
Description=AI Hub
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/ai-hub
ExecStart=/path/to/uv run ai-hub
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable ai-hub
sudo systemctl start ai-hub
```

### 3. With Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:7860;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 4. With HTTPS (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## Cloud Deployment

### Estimated Costs

| Provider | Tier | Cost/month | Users |
|----------|------|------------|-------|
| DigitalOcean | Basic 1GB | ~$6 | 1-3 |
| DigitalOcean | Basic 2GB | ~$12 | 5-10 |
| AWS EC2 | t3.small | ~$15 | 5-10 |
| Azure | B1ms | ~$15 | 5-10 |
| Hugging Face Spaces | Free | $0 | Demo only |

### Docker Deployment (Optional)

```dockerfile
FROM python:3.13-slim

WORKDIR /app
COPY . .

RUN pip install uv && uv sync

EXPOSE 7860
CMD ["uv", "run", "ai-hub"]
```

```bash
docker build -t ai-hub .
docker run -p 7860:7860 -v $(pwd)/.data:/app/.data ai-hub
```

---

## Performance Tips

1. **Disable voice** if not needed (saves ~7 GB disk, ~500 MB RAM)
2. **Use SSD** for better database performance
3. **Set concurrency limits** in Gradio for controlled resource usage
4. **Monitor memory** with `htop` or similar tools
5. **Use a reverse proxy** (nginx) for production

---

## Security Checklist

- [ ] Change default admin password
- [ ] Use HTTPS in production
- [ ] Restrict network access (firewall)
- [ ] Regular backups of `.data/` directory
- [ ] Keep dependencies updated

---

## Backup & Restore

### Backup

```bash
# Backup database and uploads
tar -czf ai-hub-backup-$(date +%Y%m%d).tar.gz .data/
```

### Restore

```bash
# Restore from backup
tar -xzf ai-hub-backup-YYYYMMDD.tar.gz
```

---

[← Back to Documentation](README.md)
