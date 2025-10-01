#!/bin/bash

# uninstall.sh - Gỡ cài đặt NORONCLIENT khỏi Ubuntu Server
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

# Confirmation
echo -e "${YELLOW}This will completely remove NORONCLIENT from your system.${NC}"
echo -e "${YELLOW}This action cannot be undone!${NC}"
echo ""
read -p "Are you sure you want to continue? (yes/no): " confirm

if [[ $confirm != "yes" ]]; then
    log_info "Uninstall cancelled."
    exit 0
fi

log_info "Starting NORONCLIENT uninstallation..."

# Stop and disable services
log_info "Stopping services..."
sudo systemctl stop ${SERVICE_NAME} 2>/dev/null || true
sudo systemctl disable ${SERVICE_NAME} 2>/dev/null || true

# Remove systemd service
log_info "Removing systemd service..."
sudo rm -f /etc/systemd/system/${SERVICE_NAME}.service
sudo systemctl daemon-reload

# Remove nginx configuration
log_info "Removing nginx configuration..."
sudo rm -f /etc/nginx/sites-enabled/${SERVICE_NAME}
sudo rm -f /etc/nginx/sites-available/${SERVICE_NAME}
sudo systemctl reload nginx

# Remove management scripts
log_info "Removing management scripts..."
sudo rm -f /usr/local/bin/${SERVICE_NAME}-ctl
sudo rm -f /usr/local/bin/${SERVICE_NAME}-backup

# Remove logrotate configuration
log_info "Removing logrotate configuration..."
sudo rm -f /etc/logrotate.d/${SERVICE_NAME}

# Remove cron jobs
log_info "Removing cron jobs..."
sudo crontab -u root -l 2>/dev/null | grep -v "${SERVICE_NAME}-backup" | sudo crontab -u root - 2>/dev/null || true

# Remove application user and directory
log_info "Removing application user and directory..."
if id "$APP_USER" &>/dev/null; then
    sudo userdel -r "$APP_USER" 2>/dev/null || true
    log_success "User $APP_USER removed"
else
    log_warning "User $APP_USER does not exist"
fi

# Remove application directory
if [ -d "$APP_DIR" ]; then
    log_info "Removing application directory..."
    sudo rm -rf "$APP_DIR"
    log_success "Application directory removed"
else
    log_warning "Application directory does not exist"
fi

# Remove backups (optional)
if [ -d "/opt/backups/$SERVICE_NAME" ]; then
    echo ""
    read -p "Remove backup files? (yes/no): " remove_backups
    if [[ $remove_backups == "yes" ]]; then
        sudo rm -rf "/opt/backups/$SERVICE_NAME"
        log_success "Backup files removed"
    else
        log_info "Backup files preserved at /opt/backups/$SERVICE_NAME"
    fi
fi

# Clean up any remaining files
log_info "Cleaning up remaining files..."
sudo find /var/log -name "*${SERVICE_NAME}*" -delete 2>/dev/null || true
sudo find /tmp -name "*${SERVICE_NAME}*" -delete 2>/dev/null || true

log_success "NORONCLIENT has been completely removed from your system!"
echo ""
echo "Removed components:"
echo "  - Service: $SERVICE_NAME"
echo "  - User: $APP_USER"
echo "  - Directory: $APP_DIR"
echo "  - Nginx configuration"
echo "  - Management scripts"
echo "  - Logrotate configuration"
echo "  - Cron jobs"
echo ""
echo "Note: System packages (Python, nginx, etc.) were not removed."
echo "If you want to remove them, run:"
echo "  sudo apt remove python3.11 nginx supervisor ufw"
