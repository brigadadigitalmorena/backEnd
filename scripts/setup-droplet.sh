#!/usr/bin/env bash
# =============================================================================
# setup-droplet.sh — One-time setup for Brigada Backend on a fresh DigitalOcean
# droplet (Ubuntu 22.04 / 24.04).
#
# Run as root:
#   curl -fsSL https://raw.githubusercontent.com/brigadadigitalmorena/backEnd/main/scripts/setup-droplet.sh | bash
# or:
#   bash scripts/setup-droplet.sh
# =============================================================================
set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
APP_USER="polo"
APP_DIR="/opt/brigada-backend"
REPO_URL="${REPO_URL:-https://github.com/brigadadigitalmorena/backEnd.git}"
PYTHON_VERSION="3.12"
SERVICE_NAME="brigada-backend"
# ─────────────────────────────────────────────────────────────────────────────

if [[ $EUID -ne 0 ]]; then
  echo "❌  Run as root (sudo bash $0)" && exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Brigada Backend — Droplet Setup"
echo " Repo : $REPO_URL"
echo " Dir  : $APP_DIR"
echo " User : $APP_USER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. System deps ─────────────────────────────────────────────────────────
echo "▶ Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
  nginx certbot python3-certbot-nginx \
  git curl ufw fail2ban

# ── 2. Swap (critical on 1 GB droplet) ────────────────────────────────────
if ! swapon --show | grep -q /swapfile; then
  echo "▶ Creating 1 GB swapfile (essential on 1 GB RAM droplet)..."
  fallocate -l 1G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
  # Reduce swappiness — only use swap under real memory pressure
  echo 'vm.swappiness=10' >> /etc/sysctl.conf
  echo 'vm.vfs_cache_pressure=50' >> /etc/sysctl.conf
  sysctl -p
  echo "   Swap enabled: $(swapon --show)"
else
  echo "▶ Swap already configured, skipping."
fi

# ── 3. Clone repo ───────────────────────────────────────────────────────────
if [[ ! -d "$APP_DIR/.git" ]]; then
  echo "▶ Cloning repository..."
  git clone "$REPO_URL" "$APP_DIR"
  chown -R "$APP_USER":"$APP_USER" "$APP_DIR"
else
  echo "▶ Repo already cloned, pulling latest..."
  cd "$APP_DIR" && git pull origin main
fi

# ── 4. Python venv + deps ───────────────────────────────────────────────────
echo "▶ Creating Python venv..."
cd "$APP_DIR"
sudo -u "$APP_USER" python${PYTHON_VERSION} -m venv venv
sudo -u "$APP_USER" venv/bin/pip install --quiet --upgrade pip
sudo -u "$APP_USER" venv/bin/pip install --quiet -r requirements.txt

# ── 5. .env file ────────────────────────────────────────────────────────────
if [[ ! -f "$APP_DIR/.env" ]]; then
  echo "▶ Creating .env from template..."
  cat > "$APP_DIR/.env" << 'EOF'
# ── Fill in all values before starting the service ──────────────────────────
DATABASE_URL=postgresql://brigada:<password>@<host>.neon.tech/brigada?sslmode=require
SECRET_KEY=CHANGE_ME_use_openssl_rand_hex_32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
ENVIRONMENT=production
ALLOWED_ORIGINS=https://psic-danieladiaz.com,https://web-cms-murex.vercel.app
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
CLOUDINARY_URL=
EOF
  chown "$APP_USER":"$APP_USER" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo ""
  echo "⚠️  Edit $APP_DIR/.env before starting the service!"
  echo "   Run: nano $APP_DIR/.env"
fi

# ── 6. systemd service ──────────────────────────────────────────────────────
echo "▶ Installing systemd service..."
cp "$APP_DIR/scripts/brigada-backend.service" "/etc/systemd/system/${SERVICE_NAME}.service"
# Allow brigada user to restart its own service without password
echo "$APP_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart ${SERVICE_NAME}, /bin/systemctl start ${SERVICE_NAME}, /bin/systemctl stop ${SERVICE_NAME}" \
  > "/etc/sudoers.d/${APP_USER}-service"
chmod 440 "/etc/sudoers.d/${APP_USER}-service"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

# ── 7. Firewall ─────────────────────────────────────────────────────────────
echo "▶ Configuring UFW firewall..."
ufw allow OpenSSH
ufw allow "Nginx Full"
ufw --force enable

# ── 8. SSH deploy key for GitHub Actions ────────────────────────────────────
DEPLOY_KEY="$APP_DIR/.ssh/deploy_key"
if [[ ! -f "$DEPLOY_KEY" ]]; then
  echo "▶ Generating deploy SSH key..."
  mkdir -p "$APP_DIR/.ssh"
  ssh-keygen -t ed25519 -C "github-actions-deploy" -f "$DEPLOY_KEY" -N ""
  chown -R "$APP_USER":"$APP_USER" "$APP_DIR/.ssh"
  chmod 700 "$APP_DIR/.ssh"
  chmod 600 "$DEPLOY_KEY"
  # Allow this key to SSH in as the app user
  cat "${DEPLOY_KEY}.pub" >> "$APP_DIR/.ssh/authorized_keys"
  chmod 600 "$APP_DIR/.ssh/authorized_keys"
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo " Add this PRIVATE key as GitHub Secret → DO_SSH_KEY:"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  cat "$DEPLOY_KEY"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ✅  Setup complete! Next steps:"
echo ""
echo "  1. Edit the .env file:"
echo "       nano $APP_DIR/.env"
echo ""
echo "  2. Run migrations:"
echo "       cd $APP_DIR && sudo -u $APP_USER venv/bin/alembic upgrade head"
echo ""
echo "  3. Start the service:"
echo "       systemctl start $SERVICE_NAME"
echo "       systemctl status $SERVICE_NAME"
echo ""
echo "  4. Add these GitHub Secrets (repo Settings → Secrets → Actions):"
echo "       DO_HOST    → $(curl -s ifconfig.me 2>/dev/null || echo '<droplet-ip>')"
echo "       DO_USER    → $APP_USER"
echo "       DO_SSH_KEY → (printed above)"
echo "       APP_DIR    → $APP_DIR  (optional, this is the default)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
