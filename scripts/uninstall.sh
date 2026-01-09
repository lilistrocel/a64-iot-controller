#!/bin/bash
#
# A64 IoT Controller - Uninstallation Script
#
# This script removes the A64 IoT Controller from the system.
# Run as root or with sudo.
#
# Usage: sudo bash uninstall.sh
#

set -e

# Configuration (must match install.sh)
INSTALL_DIR="/opt/a64-iot-controller"
SERVICE_NAME="a64-iot-controller"
SERVICE_USER="a64iot"
DATA_DIR="/var/lib/a64-iot-controller"
LOG_DIR="/var/log/a64-iot-controller"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

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
    echo_error "Please run as root (sudo bash uninstall.sh)"
    exit 1
fi

echo "========================================"
echo "  A64 IoT Controller - Uninstallation"
echo "========================================"
echo ""

# Confirm
read -p "This will remove the A64 IoT Controller. Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Stop and disable service
echo_info "Stopping service..."
systemctl stop $SERVICE_NAME 2>/dev/null || true
systemctl disable $SERVICE_NAME 2>/dev/null || true

# Remove systemd service file
echo_info "Removing systemd service..."
rm -f /etc/systemd/system/$SERVICE_NAME.service
systemctl daemon-reload

# Remove installation directory
echo_info "Removing installation directory..."
rm -rf $INSTALL_DIR

# Ask about data
read -p "Remove database and logs? This will delete all data! (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo_info "Removing data directory..."
    rm -rf $DATA_DIR
    echo_info "Removing log directory..."
    rm -rf $LOG_DIR
else
    echo_info "Keeping data in $DATA_DIR"
    echo_info "Keeping logs in $LOG_DIR"
fi

# Ask about user
read -p "Remove service user ($SERVICE_USER)? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo_info "Removing service user..."
    userdel $SERVICE_USER 2>/dev/null || true
else
    echo_info "Keeping service user $SERVICE_USER"
fi

echo ""
echo "========================================"
echo "  Uninstallation Complete!"
echo "========================================"
echo ""
