#!/bin/bash
# Multilevel Mock Test - VPS deploy script
# Ishga tushirish: sudo bash deploy.sh
# Oldin: loyha fayllarini /var/www/mocktest papkasiga ko'chiring
set -e

APP_DIR="/var/www/mocktest"
DOMAIN="multilevelmocktest.uz"

echo "=== 1. Paketlarni o'rnatish ==="
apt-get update -y
apt-get install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx

echo "=== 2. Loyha papkasini yaratish ==="
mkdir -p "$APP_DIR"
chown -R www-data:www-data "$APP_DIR"

echo "=== 3. Python virtual environment ==="
if [ ! -d "$APP_DIR/venv" ]; then
    python3 -m venv "$APP_DIR/venv"
fi
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "=== 4. Systemd xizmati ==="
cp "$APP_DIR/deploy/mocktest.service" /etc/systemd/system/mocktest.service
systemctl daemon-reload
systemctl enable mocktest
systemctl restart mocktest

echo "=== 5. Nginx sozlash ==="
cp "$APP_DIR/deploy/nginx-mocktest.conf" /etc/nginx/sites-available/mocktest
ln -sf /etc/nginx/sites-available/mocktest /etc/nginx/sites-enabled/mocktest
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "=== 6. SSL sertifikat (Let's Encrypt) ==="
certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos -m admin@$DOMAIN --redirect

echo "=== 7. Fayl huquqlari ==="
chown -R www-data:www-data "$APP_DIR"
chmod 755 "$APP_DIR"
mkdir -p "$APP_DIR/receipts"
chown -R www-data:www-data "$APP_DIR/receipts"

echo "=== Tayyor! ==="
echo "Sayt: https://$DOMAIN"
echo "Admin: https://$DOMAIN/admin"
systemctl status mocktest --no-pager
