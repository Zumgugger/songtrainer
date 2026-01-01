#!/bin/bash
# Songtrainer Deployment Script for Ubuntu Server
# Run as root: sudo bash deploy.sh

set -e

APP_DIR="/var/www/songtrainer"
APACHE_CONF="/etc/apache2/sites-available/songtrainer.zumgugger.ch.conf"

echo "=== Songtrainer Deployment ==="

# 1. Create app directory
echo "Creating app directory..."
mkdir -p $APP_DIR
cd $APP_DIR

# 2. Clone or pull latest code
if [ -d ".git" ]; then
    echo "Pulling latest changes..."
    git pull
else
    echo "Cloning repository..."
    git clone https://github.com/Zumgugger/songtrainer.git .
fi

# 3. Create data directories
echo "Creating data directories..."
mkdir -p data charts uploads

# 4. Create .env file if not exists
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo "SECRET_KEY=$SECRET" > .env
    echo "Generated new SECRET_KEY"
fi

# 5. Copy Apache config
echo "Copying Apache configuration..."
cp deploy/songtrainer.zumgugger.ch.conf $APACHE_CONF

# 6. Enable required Apache modules
echo "Enabling Apache modules..."
a2enmod proxy proxy_http rewrite ssl headers

# 7. Enable the site (without SSL first for certbot)
echo "Creating temporary HTTP-only config for certbot..."
cat > /etc/apache2/sites-available/songtrainer-temp.conf << 'EOF'
<VirtualHost *:80>
    ServerName songtrainer.zumgugger.ch
    DocumentRoot /var/www/html
</VirtualHost>
EOF

a2ensite songtrainer-temp.conf
systemctl reload apache2

# 8. Get SSL certificate
echo "Obtaining SSL certificate..."
certbot --apache -d songtrainer.zumgugger.ch --non-interactive --agree-tos --email your-email@example.com || true

# 9. Disable temp config and enable full config
a2dissite songtrainer-temp.conf
rm /etc/apache2/sites-available/songtrainer-temp.conf
a2ensite songtrainer.zumgugger.ch.conf

# 10. Test Apache config
echo "Testing Apache configuration..."
apache2ctl configtest

# 11. Build and start Docker container
echo "Building and starting Docker container..."
docker compose down || true
docker compose up -d --build

# 12. Reload Apache
echo "Reloading Apache..."
systemctl reload apache2

# 13. Check status
echo ""
echo "=== Deployment Complete ==="
echo "Checking container status..."
docker compose ps
echo ""
echo "Site should be available at: https://songtrainer.zumgugger.ch"
echo ""
echo "Useful commands:"
echo "  View logs: docker compose logs -f"
echo "  Restart:   docker compose restart"
echo "  Stop:      docker compose down"
