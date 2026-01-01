# Songtrainer Deployment Guide

## Prerequisites
- Ubuntu server with Docker and Docker Compose installed
- Apache2 installed
- Certbot installed (`apt install certbot python3-certbot-apache`)
- DNS A record pointing `songtrainer.zumgugger.ch` to your server IP

## Quick Deployment

### 1. SSH into your server
```bash
ssh root@185.66.108.95
```

### 2. Create and navigate to app directory
```bash
mkdir -p /var/www/songtrainer
cd /var/www/songtrainer
```

### 3. Clone the repository
```bash
git clone https://github.com/Zumgugger/songtrainer.git .
```

### 4. Create environment file
```bash
# Generate a secure secret key
SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
echo "SECRET_KEY=$SECRET" > .env

# Optionally set admin credentials
echo "ADMIN_EMAIL=your-email@example.com" >> .env
echo "ADMIN_PASSWORD=your-secure-password" >> .env
```

### 5. Create data directories
```bash
mkdir -p data charts uploads
```

### 6. Copy Apache config
```bash
cp deploy/songtrainer.zumgugger.ch.conf /etc/apache2/sites-available/
```

### 7. Get SSL certificate first (before enabling the full config)
```bash
# Create temporary HTTP config for certbot
cat > /etc/apache2/sites-available/songtrainer-temp.conf << 'EOF'
<VirtualHost *:80>
    ServerName songtrainer.zumgugger.ch
    DocumentRoot /var/www/html
</VirtualHost>
EOF

# Enable and reload
a2ensite songtrainer-temp.conf
systemctl reload apache2

# Get certificate (replace email)
certbot --apache -d songtrainer.zumgugger.ch

# Disable temp config
a2dissite songtrainer-temp.conf
rm /etc/apache2/sites-available/songtrainer-temp.conf
```

### 8. Enable Apache modules and site
```bash
a2enmod proxy proxy_http rewrite ssl headers
a2ensite songtrainer.zumgugger.ch.conf
apache2ctl configtest
systemctl reload apache2
```

### 9. Build and start the Docker container
```bash
docker compose up -d --build
```

### 10. Verify deployment
```bash
# Check container status
docker compose ps

# View logs
docker compose logs -f

# Test the site
curl -I https://songtrainer.zumgugger.ch
```

## Management Commands

### View logs
```bash
cd /var/www/songtrainer
docker compose logs -f
```

### Restart application
```bash
docker compose restart
```

### Stop application
```bash
docker compose down
```

### Update application
```bash
cd /var/www/songtrainer
git pull
docker compose down
docker compose up -d --build
```

### Backup database
```bash
cp /var/www/songtrainer/data/songs.db /var/www/songtrainer/data/songs.db.backup.$(date +%Y%m%d)
```

## Troubleshooting

### Check if container is running
```bash
docker compose ps
```

### Check container logs
```bash
docker compose logs --tail=100
```

### Check Apache error logs
```bash
tail -f /var/log/apache2/songtrainer_error.log
```

### Test proxy connection
```bash
curl http://127.0.0.1:5001/
```

### Rebuild container from scratch
```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```
