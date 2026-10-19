#!/usr/bin/env bash
# Put the app behind nginx on a domain, with HTTPS from Let's Encrypt (geolocation in the browser needs HTTPS).
# Run after deploy/run.sh, as root. Needs: an A record for the domain pointing at this server, and ports 80 + 443
# reachable from the internet. Safe to re-run; without DNS / open ports it sets up plain HTTP and says so.
#
#   bash deploy/nginx.sh app.example.pl [email]
set -euo pipefail
DOMAIN=${1:?usage: deploy/nginx.sh <domain> [email]}
EMAIL=${2:-}
PORT=${PORT:-8080}

command -v nginx >/dev/null && command -v certbot >/dev/null || {
  apt-get update -q && DEBIAN_FRONTEND=noninteractive apt-get install -yq nginx certbot python3-certbot-nginx; }

cat > /etc/nginx/sites-available/warsaw-open-data <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    client_max_body_size 5m;
    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
    }
}
EOF
ln -sfn /etc/nginx/sites-available/warsaw-open-data /etc/nginx/sites-enabled/warsaw-open-data
rm -f /etc/nginx/sites-enabled/default
nginx -t
if pgrep -x nginx >/dev/null; then nginx -s reload; else nginx; fi
echo "nginx: http://$DOMAIN -> 127.0.0.1:$PORT"

if getent hosts "$DOMAIN" >/dev/null; then
  certbot --nginx -n --agree-tos --redirect -d "$DOMAIN" ${EMAIL:+-m "$EMAIL"} ${EMAIL:---register-unsafely-without-email} \
    && echo "https://$DOMAIN is up" || echo "certbot failed: check that ports 80 and 443 reach this server"
else
  echo "$DOMAIN does not resolve yet: re-run this script once DNS works to get HTTPS"
fi
