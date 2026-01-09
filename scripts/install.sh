#!/bin/bash
#
# A64 IoT Controller - Installation Script
#
# This script installs and configures the A64 IoT Controller on a Raspberry Pi.
# Run as root or with sudo.
#
# Usage: sudo bash install.sh
#

set -e

# Configuration
INSTALL_DIR="/opt/a64-iot-controller"
SERVICE_NAME="a64-iot-controller"
SERVICE_USER="a64iot"
VENV_DIR="$INSTALL_DIR/venv"
DATA_DIR="/var/lib/a64-iot-controller"
LOG_DIR="/var/log/a64-iot-controller"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo_error "Please run as root (sudo bash install.sh)"
    exit 1
fi

echo "========================================"
echo "  A64 IoT Controller - Installation"
echo "========================================"
echo ""

# Check Python version
echo_info "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]); then
    echo_error "Python 3.9+ is required. Found: Python $PYTHON_VERSION"
    exit 1
fi
echo_info "Found Python $PYTHON_VERSION"

# Install system dependencies
echo_info "Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3-pip python3-venv git

# Create service user if not exists
if ! id "$SERVICE_USER" &>/dev/null; then
    echo_info "Creating service user: $SERVICE_USER"
    useradd --system --no-create-home --shell /bin/false $SERVICE_USER
else
    echo_info "Service user $SERVICE_USER already exists"
fi

# Create directories
echo_info "Creating directories..."
mkdir -p $INSTALL_DIR
mkdir -p $DATA_DIR
mkdir -p $LOG_DIR

# Copy application files
echo_info "Copying application files..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cp -r "$PROJECT_DIR/src" "$INSTALL_DIR/"
cp "$PROJECT_DIR/requirements.txt" "$INSTALL_DIR/"
cp "$PROJECT_DIR/.env.example" "$INSTALL_DIR/"

# Create .env if not exists
if [ ! -f "$INSTALL_DIR/.env" ]; then
    echo_info "Creating default .env configuration..."
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"

    # Generate random API key
    API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    sed -i "s/API_KEY=.*/API_KEY=$API_KEY/" "$INSTALL_DIR/.env"

    # Set paths
    sed -i "s|DATABASE_PATH=.*|DATABASE_PATH=$DATA_DIR/iot_controller.db|" "$INSTALL_DIR/.env"
    sed -i "s|LOG_FILE=.*|LOG_FILE=$LOG_DIR/controller.log|" "$INSTALL_DIR/.env"
else
    echo_info "Keeping existing .env configuration"
fi

# Create Python virtual environment
echo_info "Creating Python virtual environment..."
python3 -m venv $VENV_DIR

# Install Python dependencies
echo_info "Installing Python dependencies..."
$VENV_DIR/bin/pip install --upgrade pip -q
$VENV_DIR/bin/pip install -r $INSTALL_DIR/requirements.txt -q

# Set permissions
echo_info "Setting permissions..."
chown -R $SERVICE_USER:$SERVICE_USER $INSTALL_DIR
chown -R $SERVICE_USER:$SERVICE_USER $DATA_DIR
chown -R $SERVICE_USER:$SERVICE_USER $LOG_DIR
chmod 750 $DATA_DIR
chmod 750 $LOG_DIR
chmod 640 $INSTALL_DIR/.env

# Create systemd service
echo_info "Creating systemd service..."
cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=A64 IoT Controller
After=network.target
Wants=network-online.target

[Service]
Type=notify
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/python -m src.main
Restart=always
RestartSec=10
WatchdogSec=60

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$DATA_DIR $LOG_DIR
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
echo_info "Reloading systemd..."
systemctl daemon-reload

# Enable service
echo_info "Enabling service..."
systemctl enable $SERVICE_NAME

echo ""
echo "========================================"
echo "  Installation Complete!"
echo "========================================"
echo ""
echo "Configuration file: $INSTALL_DIR/.env"
echo "Database location:  $DATA_DIR/iot_controller.db"
echo "Log file:           $LOG_DIR/controller.log"
echo ""
echo "Commands:"
echo "  Start service:    sudo systemctl start $SERVICE_NAME"
echo "  Stop service:     sudo systemctl stop $SERVICE_NAME"
echo "  View status:      sudo systemctl status $SERVICE_NAME"
echo "  View logs:        sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "API will be available at: http://localhost:8000"
echo "API docs at: http://localhost:8000/api/docs"
echo ""
echo "IMPORTANT: Edit $INSTALL_DIR/.env to configure your gateways!"
echo ""
