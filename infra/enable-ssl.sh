#!/bin/bash
# Run this once DNS for app.workbai.autorepairsolutions.ai points to 167.99.153.77
DOMAIN=app.workbai.autorepairsolutions.ai
EMAIL=carl@autorepairsolutions.ai

certbot certonly --webroot -w /var/www/certbot   -d  --email    --agree-tos --non-interactive

if [ -f /etc/letsencrypt/live//fullchain.pem ]; then
  cp /etc/letsencrypt/live//fullchain.pem /etc/ssl/workbay/fullchain.pem
  cp /etc/letsencrypt/live//privkey.pem /etc/ssl/workbay/privkey.pem
  docker compose -f /root/workbai/docker-compose.yml restart nginx
  echo 'SSL enabled successfully'
else
  echo 'Cert not found — check DNS and try again'
fi
