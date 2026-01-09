# A64 IoT Controller

IoT device management and automation system for Raspberry Pi. Controls sensors and relays via RS485-to-Ethernet gateways using Modbus protocol.

## Features

- **Device Management**: Configure and manage RS485-ETH gateways, sensors, and relay controllers
- **Real-time Monitoring**: Track sensor readings and relay states
- **Automation**: Schedule-based and trigger-based relay control
- **Fault Tolerance**: SQLite with WAL mode, automatic recovery after power outages
- **REST API**: FastAPI-based API with OpenAPI documentation
- **Autonomous Operation**: Works offline, syncs with A64Core when connected

## Requirements

- Raspberry Pi (3B+ or newer recommended)
- Python 3.9+
- RS485-to-Ethernet gateway (e.g., Waveshare)
- Modbus RTU sensors and/or relay controllers

## Quick Start

### Development

```bash
# Clone the repository
git clone https://github.com/lilistrocel/a64-iot-controller.git
cd a64-iot-controller

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy and edit configuration
cp .env.example .env
nano .env

# Run in development mode
bash scripts/run_dev.sh
# or: uvicorn src.main:app --reload
```

### Production Installation

```bash
# On Raspberry Pi
sudo bash scripts/install.sh

# Edit configuration
sudo nano /opt/a64-iot-controller/.env

# Start the service
sudo systemctl start a64-iot-controller

# View logs
sudo journalctl -u a64-iot-controller -f
```

## API Documentation

Once running, access the API documentation at:
- Swagger UI: `http://<pi-ip>:8000/api/docs`
- ReDoc: `http://<pi-ip>:8000/api/redoc`

### Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health check |
| `GET /api/gateways` | List RS485 gateways |
| `GET /api/devices` | List all devices |
| `GET /api/channels` | List all channels |
| `GET /api/readings` | Latest sensor readings |
| `GET /api/relays` | Relay states |
| `PUT /api/relays/{id}` | Control a relay |
| `GET /api/schedules` | List schedules |
| `GET /api/triggers` | List triggers |

## Configuration

Edit `.env` file to configure:

```env
# API Settings
API_HOST=0.0.0.0
API_PORT=8000
API_KEY=your-secret-key

# Database
DATABASE_PATH=/var/lib/a64-iot-controller/iot_controller.db

# Default Gateway (optional)
DEFAULT_GATEWAY_HOST=192.168.1.100
DEFAULT_GATEWAY_PORT=502

# Polling intervals
SENSOR_POLL_INTERVAL=30
RELAY_POLL_INTERVAL=5

# Recovery
RECOVER_RELAY_STATES=true
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    A64 IoT Controller                    │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │  REST API   │  │  Automation │  │ Device Manager  │  │
│  │  (FastAPI)  │  │   Engine    │  │   (Modbus)      │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
│         │                │                  │           │
│         └────────────────┼──────────────────┘           │
│                          │                              │
│                 ┌────────┴────────┐                     │
│                 │  SQLite (WAL)   │                     │
│                 └─────────────────┘                     │
└─────────────────────────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │   RS485-ETH Gateway     │
              └────────────┬────────────┘
                           │ RS485
           ┌───────────────┼───────────────┐
           │               │               │
     ┌─────┴─────┐   ┌─────┴─────┐   ┌─────┴─────┐
     │  Sensor   │   │  Sensor   │   │   Relay   │
     │ (Addr 1)  │   │ (Addr 2)  │   │ (Addr 3)  │
     └───────────┘   └───────────┘   └───────────┘
```

## Project Structure

```
a64-iot-controller/
├── src/
│   ├── __init__.py
│   ├── main.py              # Application entry point
│   ├── config.py            # Configuration settings
│   ├── api/                  # REST API endpoints
│   │   ├── __init__.py
│   │   ├── deps.py          # Dependencies (auth, db)
│   │   ├── health.py
│   │   ├── gateways.py
│   │   ├── devices.py
│   │   ├── channels.py
│   │   ├── readings.py
│   │   ├── relays.py
│   │   ├── schedules.py
│   │   ├── triggers.py
│   │   └── discovery.py
│   ├── core/                 # Core modules
│   │   ├── __init__.py
│   │   ├── database.py      # SQLite database
│   │   └── models.py        # Pydantic models
│   └── startup/
│       ├── __init__.py
│       └── recovery.py      # Boot recovery
├── scripts/
│   ├── install.sh           # Production installer
│   ├── uninstall.sh
│   └── run_dev.sh           # Development runner
├── .env.example
├── requirements.txt
└── README.md
```

## License

MIT
