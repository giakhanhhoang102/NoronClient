# NORONCLIENT

Ứng dụng FlowLite cho việc xử lý các flow automation với các tính năng bảo mật và logging.

## 🚀 Cài đặt nhanh

### Trên Ubuntu Server

1. **Clone repository:**
```bash
git clone <repository-url>
cd NORONCLIENT
```

2. **Chạy script cài đặt:**
```bash
chmod +x install.sh
./install.sh
```

3. **Cấu hình:**
```bash
sudo nano /opt/noronclient/.env
```

4. **Khởi động dịch vụ:**
```bash
sudo systemctl start noronclient
sudo systemctl enable noronclient
```

## 📋 Yêu cầu hệ thống

- **OS:** Ubuntu 20.04+ / Debian 11+
- **Python:** 3.11+
- **RAM:** Tối thiểu 1GB
- **Disk:** Tối thiểu 2GB
- **Network:** Port 80, 443

## 🔧 Cấu hình

### Environment Variables

Chỉnh sửa file `/opt/noronclient/.env`:

```bash
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
DATABASE_URL=sqlite:////opt/noronclient/data/flowlite_data.db

# Logging
LOG_LEVEL=INFO
LOG_FILE=/opt/noronclient/logs/app.log

# Security
SECRET_KEY=your_secret_key_here
JWT_SECRET=your_jwt_secret_here

# Features
ENABLE_CURL_DUMP=0
ENABLE_MASK_COOKIES=1
DEBUG_TRACE=false
```

## 🎮 Quản lý dịch vụ

### Sử dụng systemctl

```bash
# Khởi động
sudo systemctl start noronclient

# Dừng
sudo systemctl stop noronclient

# Khởi động lại
sudo systemctl restart noronclient

# Xem trạng thái
sudo systemctl status noronclient

# Xem logs
sudo journalctl -u noronclient -f
```

### Sử dụng script quản lý

```bash
# Khởi động
noronclient-ctl start

# Dừng
noronclient-ctl stop

# Khởi động lại
noronclient-ctl restart

# Xem trạng thái
noronclient-ctl status

# Xem logs
noronclient-ctl logs

# Cập nhật ứng dụng
noronclient-ctl update
```

## 📁 Cấu trúc thư mục

```
/opt/noronclient/
├── app/                    # Ứng dụng chính
├── flows/                  # Các flow automation
├── flowlite/              # Framework FlowLite
├── logs/                  # Log files
├── data/                  # Database files
├── venv/                  # Python virtual environment
├── .env                   # Environment configuration
└── requirements.txt       # Python dependencies
```

## 🔒 Bảo mật

### Firewall
- Port 22 (SSH)
- Port 80 (HTTP)
- Port 443 (HTTPS)

### User Permissions
- Ứng dụng chạy với user `noronclient`
- Không có quyền root
- Isolated environment

### Logging
- Tất cả logs được ghi vào systemd journal
- Log rotation tự động (30 ngày)
- Sensitive data được mask

## 📊 Monitoring

### Health Check
```bash
curl http://localhost/health
```

### Logs
```bash
# System logs
sudo journalctl -u noronclient -f

# Application logs
tail -f /opt/noronclient/logs/app.log
```

### Status
```bash
# Service status
sudo systemctl status noronclient

# Nginx status
sudo systemctl status nginx

# Disk usage
df -h /opt/noronclient
```

## 🔄 Backup & Restore

### Tự động backup
- Backup hàng ngày lúc 2:00 AM
- Lưu tại `/opt/backups/noronclient/`
- Giữ lại 7 backup gần nhất

### Manual backup
```bash
noronclient-ctl-backup
```

### Restore
```bash
# Dừng service
sudo systemctl stop noronclient

# Restore từ backup
sudo tar -xzf /opt/backups/noronclient/noronclient_backup_YYYYMMDD_HHMMSS.tar.gz -C /opt/noronclient/

# Khởi động lại
sudo systemctl start noronclient
```

## 🚨 Troubleshooting

### Service không khởi động
```bash
# Xem logs chi tiết
sudo journalctl -u noronclient -n 50

# Kiểm tra cấu hình
sudo systemctl status noronclient
```

### Port bị chiếm
```bash
# Kiểm tra port
sudo netstat -tlnp | grep :8000

# Kill process
sudo kill -9 <PID>
```

### Permission issues
```bash
# Fix permissions
sudo chown -R noronclient:noronclient /opt/noronclient
sudo chmod -R 755 /opt/noronclient
```

## 🔄 Cập nhật

### Cập nhật ứng dụng
```bash
noronclient-ctl update
```

### Cập nhật system packages
```bash
sudo apt update && sudo apt upgrade -y
sudo systemctl restart noronclient
```

## 🗑️ Gỡ cài đặt

```bash
chmod +x uninstall.sh
./uninstall.sh
```

## 📞 Hỗ trợ

- **Logs:** `/opt/noronclient/logs/`
- **Config:** `/opt/noronclient/.env`
- **Service:** `noronclient.service`
- **Nginx:** `/etc/nginx/sites-available/noronclient`

## 📝 Changelog

### v1.0.0
- Initial release
- Systemd service integration
- Nginx reverse proxy
- Automatic backup
- Security hardening
- Log rotation
- Management scripts

## 📄 License

[Your License Here]

---

**Lưu ý:** Đảm bảo cập nhật `TLS_AUTH_TOKEN` trong file `.env` trước khi sử dụng trong production.