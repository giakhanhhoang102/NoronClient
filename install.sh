#!/bin/bash

# install.sh - Cài đặt NORONCLIENT trên Ubuntu Server
# Tác giả: Auto-generated
# Ngày: $(date +%Y-%m-%d)

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="noronclient"
APP_USER="noronclient"
APP_DIR="/opt/noronclient"
SERVICE_NAME="noronclient"
PYTHON_VERSION="3.11"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   log_error "This script should not be run as root. Please run as a regular user with sudo privileges."
   exit 1
fi

# Check if sudo is available
if ! command -v sudo &> /dev/null; then
    log_error "sudo is not installed. Please install sudo first."
    exit 1
fi

log_info "Starting NORONCLIENT installation..."

# Update system packages
log_info "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install required system packages
log_info "Installing system dependencies..."
sudo apt install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    git \
    curl \
    wget \
    unzip \
    build-essential \
    libssl-dev \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg-dev \
    libpng-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libxcb1-dev \
    ufw

# Create application user
log_info "Creating application user..."
if ! id "$APP_USER" &>/dev/null; then
    sudo useradd -r -s /bin/false -d "$APP_DIR" -m "$APP_USER"
    log_success "User $APP_USER created"
else
    log_warning "User $APP_USER already exists"
fi

# Create application directory
log_info "Creating application directory..."
sudo mkdir -p "$APP_DIR"
sudo chown "$APP_USER:$APP_USER" "$APP_DIR"

# Copy application files
log_info "Copying application files..."
sudo cp -r . "$APP_DIR/"
sudo chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# Create Python virtual environment
log_info "Creating Python virtual environment..."
sudo -u "$APP_USER" python3.11 -m venv "$APP_DIR/venv"

# Activate virtual environment and install dependencies
log_info "Installing Python dependencies..."
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

# Create logs directory
log_info "Creating logs directory..."
sudo mkdir -p "$APP_DIR/logs"
sudo chown -R "$APP_USER:$APP_USER" "$APP_DIR/logs"

# Create systemd service file
log_info "Creating systemd service..."
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOF
[Unit]
Description=NORONCLIENT Application
After=network.target
Wants=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
Environment=PYTHONPATH=$APP_DIR
Environment=ENABLE_CURL_DUMP=0
Environment=ENABLE_MASK_COOKIES=1
Environment=DEBUG_TRACE=false
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/uvicorn app.main:app --host ${HOST} --port ${PORT} --workers ${WORKERS}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$APP_DIR
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true

[Install]
WantedBy=multi-user.target
EOF

# Configure firewall
log_info "Configuring firewall..."
sudo ufw --force enable
sudo ufw allow ssh
sudo ufw allow 8000/tcp

# Create logrotate configuration
log_info "Creating logrotate configuration..."
sudo tee /etc/logrotate.d/${SERVICE_NAME} > /dev/null <<EOF
$APP_DIR/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $APP_USER $APP_USER
    postrotate
        systemctl reload $SERVICE_NAME
    endscript
}
EOF

# Create environment file
log_info "Creating environment configuration..."
sudo tee "$APP_DIR/.env" > /dev/null <<EOF
# NORONCLIENT Environment Configuration
DEBUG=false
HOST=127.0.0.1
PORT=8000
WORKERS=4

# TLS Configuration
TLS_BASE=http://127.0.0.1:3000
TLS_AUTH_HEADER=X-Auth-Token
TLS_AUTH_TOKEN=your_tls_token_here

# Database
DATABASE_URL=sqlite:///$APP_DIR/data/flowlite_data.db

# Logging
LOG_LEVEL=INFO
LOG_FILE=$APP_DIR/logs/app.log

# Security
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET=$(openssl rand -hex 32)

# Features
ENABLE_CURL_DUMP=0
ENABLE_MASK_COOKIES=1
DEBUG_TRACE=false
EOF

sudo chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
sudo chmod 600 "$APP_DIR/.env"

# Create data directory
sudo mkdir -p "$APP_DIR/data"
sudo chown -R "$APP_USER:$APP_USER" "$APP_DIR/data"

# Reload systemd and start services
log_info "Starting services..."
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl start ${SERVICE_NAME}

# Wait for service to start
sleep 5

# Check service status
if sudo systemctl is-active --quiet ${SERVICE_NAME}; then
    log_success "Service $SERVICE_NAME is running"
else
    log_error "Service $SERVICE_NAME failed to start"
    sudo systemctl status ${SERVICE_NAME}
    exit 1
fi

# Create management script
log_info "Creating management script..."
sudo tee /usr/local/bin/${SERVICE_NAME}-ctl > /dev/null <<EOF
#!/bin/bash
# NORONCLIENT Management Script

case "\$1" in
    start)
        sudo systemctl start $SERVICE_NAME
        echo "Service started"
        ;;
    stop)
        sudo systemctl stop $SERVICE_NAME
        echo "Service stopped"
        ;;
    restart)
        sudo systemctl restart $SERVICE_NAME
        echo "Service restarted"
        ;;
    status)
        sudo systemctl status $SERVICE_NAME
        ;;
    logs)
        sudo journalctl -u $SERVICE_NAME -f
        ;;
    update)
        cd $APP_DIR
        sudo -u $APP_USER git pull
        sudo -u $APP_USER $APP_DIR/venv/bin/pip install -r requirements.txt
        sudo systemctl restart $SERVICE_NAME
        echo "Application updated and restarted"
        ;;
    *)
        echo "Usage: $SERVICE_NAME-ctl {start|stop|restart|status|logs|update}"
        exit 1
        ;;
esac
EOF

sudo chmod +x /usr/local/bin/${SERVICE_NAME}-ctl

# Create backup script
log_info "Creating backup script..."
sudo tee /usr/local/bin/${SERVICE_NAME}-backup > /dev/null <<EOF
#!/bin/bash
# NORONCLIENT Backup Script

BACKUP_DIR="/opt/backups/$SERVICE_NAME"
DATE=\$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="\$BACKUP_DIR/${SERVICE_NAME}_backup_\$DATE.tar.gz"

mkdir -p "\$BACKUP_DIR"

tar -czf "\$BACKUP_FILE" -C $APP_DIR \
    --exclude=venv \
    --exclude=__pycache__ \
    --exclude=*.pyc \
    --exclude=.git \
    .

echo "Backup created: \$BACKUP_FILE"

# Keep only last 7 backups
find "\$BACKUP_DIR" -name "${SERVICE_NAME}_backup_*.tar.gz" -mtime +7 -delete
EOF

sudo chmod +x /usr/local/bin/${SERVICE_NAME}-backup

# Create cron job for backup
log_info "Setting up backup cron job..."
echo "0 2 * * * /usr/local/bin/${SERVICE_NAME}-backup" | sudo crontab -u root -

# Final status check
log_info "Performing final status check..."
if curl -s http://localhost:8000/health > /dev/null; then
    log_success "Application is responding to health checks"
else
    log_warning "Application health check failed - check logs"
fi

# Display installation summary
echo ""
echo "=========================================="
log_success "NORONCLIENT Installation Complete!"
echo "=========================================="
echo ""
echo "Service Information:"
echo "  - Service Name: $SERVICE_NAME"
echo "  - Application Directory: $APP_DIR"
echo "  - User: $APP_USER"
echo "  - Web Interface: http://$(curl -s ifconfig.me)/"
echo ""
echo "Management Commands:"
echo "  - Start:   sudo systemctl start $SERVICE_NAME"
echo "  - Stop:    sudo systemctl stop $SERVICE_NAME"
echo "  - Restart: sudo systemctl restart $SERVICE_NAME"
echo "  - Status:  sudo systemctl status $SERVICE_NAME"
echo "  - Logs:    sudo journalctl -u $SERVICE_NAME -f"
echo "  - Control: $SERVICE_NAME-ctl {start|stop|restart|status|logs|update}"
echo "  - Backup:  $SERVICE_NAME-ctl-backup"
echo ""
echo "Configuration Files:"
echo "  - Service: /etc/systemd/system/${SERVICE_NAME}.service"
echo "  - Env:     $APP_DIR/.env"
echo ""
echo "Next Steps:"
echo "1. Edit $APP_DIR/.env to configure your settings"
echo "2. Update TLS_AUTH_TOKEN in the environment file"
echo "3. Restart the service: sudo systemctl restart $SERVICE_NAME"
echo "4. Check logs: sudo journalctl -u $SERVICE_NAME -f"
echo ""
log_success "Installation completed successfully!"
