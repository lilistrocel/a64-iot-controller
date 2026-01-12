# A64 IoT Controller - AI Agent Guide

## Project Overview

This is an IoT controller system running on a Raspberry Pi that manages sensors and relay controllers via RS485/Modbus protocol. It serves as a bridge between physical IoT hardware and the A64Core Platform cloud application.

## Key Concepts

### Hardware Stack
```
[Raspberry Pi] → [RS485-ETH Gateway] → [RS485 Bus] → [Sensors/Relays]
     │
     └── Cloudflare Tunnel → Internet → A64Core Platform
```

### Device Types
1. **Gateways**: RS485-to-Ethernet converters (e.g., Waveshare) that translate Modbus TCP to Modbus RTU
2. **Sensors**: Environmental sensors (temperature, humidity, soil NPK, etc.) with Modbus addresses
3. **Relay Controllers**: ESP32 or similar boards with 6+ relay channels for controlling fans, pumps, etc.

### Communication Protocol
- **Modbus RTU** over RS485 for device communication
- **Modbus TCP** from Pi to RS485-ETH gateway
- **REST API** for external access (A64Core Platform, dashboard)

## Project Structure

```
a64-iot-controller/
├── src/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Pydantic settings (loads from .env)
│   ├── api/                  # REST API endpoints
│   │   ├── __init__.py      # Router aggregation
│   │   ├── deps.py          # Dependency injection (DB, auth)
│   │   ├── health.py        # GET /api/health, /api/status
│   │   ├── gateways.py      # CRUD for RS485 gateways
│   │   ├── devices.py       # CRUD for sensors/relays
│   │   ├── channels.py      # Sensor/relay channels
│   │   ├── readings.py      # Sensor data + history
│   │   ├── relays.py        # Relay state + control
│   │   ├── schedules.py     # Time-based automation
│   │   ├── triggers.py      # Sensor-based automation
│   │   ├── discovery.py     # Auto-discover Modbus devices
│   │   ├── models.py        # Model mappings for sensors
│   │   └── a64core.py       # A64Core Platform integration endpoint
│   ├── core/
│   │   ├── database.py      # SQLite with aiosqlite (WAL mode)
│   │   └── models.py        # Pydantic schemas
│   ├── devices/
│   │   └── device_manager.py # Modbus polling & relay control
│   ├── scheduler/
│   │   └── scheduler.py     # Schedule & trigger execution
│   ├── startup/
│   │   └── recovery.py      # Boot-time relay state recovery
│   └── static/              # Web dashboard
│       ├── index.html       # Alpine.js dashboard
│       ├── css/dashboard.css
│       └── js/
│           ├── api.js       # API client with auth
│           └── app.js       # Alpine.js store & logic
├── data/
│   └── controller.db        # SQLite database
├── models/                   # Sensor model definitions (YAML)
├── scripts/
│   ├── install.sh           # Systemd service installation
│   └── run_dev.sh           # Development runner
├── .env                     # Configuration (not in git)
└── requirements.txt
```

## Database Schema

### Key Tables
- **gateways**: RS485-ETH gateway connections
- **devices**: Sensors and relay controllers
- **channels**: Individual sensor channels or relay outputs
- **readings**: Historical sensor data
- **relay_states**: Current relay states with source tracking
- **schedules**: Time-based automation rules
- **triggers**: Sensor-based automation rules

### Important: WAL Mode
The database uses SQLite WAL (Write-Ahead Logging) for:
- Concurrent reads during writes
- Crash recovery
- Better performance

## API Endpoints

### Public (No Auth Required)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | System health check |
| `/api/status` | GET | Detailed system status |
| `/api/readings` | GET | Latest sensor readings |
| `/api/a64core` | GET | Aggregated data for A64Core Platform |

### Protected (X-API-Key Header Required)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/relays/{id}` | PUT | Control a relay |
| `/api/schedules` | POST | Create schedule |
| `/api/triggers` | POST | Create trigger |
| `/api/devices` | POST | Add device |
| `/api/gateways` | POST | Add gateway |

### A64Core Integration Endpoint
**GET /api/a64core** returns aggregated data in format expected by BlockAutomationTab:
```json
{
  "controllerId": "iot-controller-1",
  "controllerName": "A64 IoT Controller",
  "lastUpdate": "2026-01-10T12:00:00",
  "sensors": [
    {
      "id": "uuid",
      "name": "Air Temp/Humidity Sensor",
      "type": "sensor",
      "label": "Air Temp/Humidity Sensor",
      "online": true,
      "readings": {
        "Air Temperature": {"value": 24.5, "unit": "C"},
        "Air Humidity": {"value": 65.2, "unit": "%"}
      }
    }
  ],
  "relays": [
    {
      "id": "uuid",
      "label": "Fan 1",
      "state": false,
      "online": true
    }
  ]
}
```

## Configuration

### Environment Variables (.env)
```env
# Controller Identity
CONTROLLER_ID=iot-controller-1
CONTROLLER_NAME=A64 IoT Controller

# API Server
API_HOST=0.0.0.0
API_PORT=8000
API_KEY=your-secret-api-key  # Required for relay control

# Database
DATABASE_PATH=data/controller.db

# Polling Intervals (seconds)
SENSOR_POLL_INTERVAL=30
RELAY_POLL_INTERVAL=5

# Recovery
RECOVER_RELAY_STATES=true
```

### API Key Authentication
- Set `API_KEY` in `.env` to require authentication
- Pass key via `X-API-Key` header
- Required for: relay control, schedule/trigger management
- Not required for: health checks, sensor readings

## Background Tasks

### Sensor Polling Loop
- Runs every `SENSOR_POLL_INTERVAL` seconds
- Queries all sensor devices via Modbus
- Stores readings in database
- Updates device online status

### Relay Control Loop
- Runs every `RELAY_POLL_INTERVAL` seconds
- Executes pending relay commands from queue
- Sends Modbus write commands to relay controllers
- Updates device online status on success

### Scheduler Loop
- Checks schedules every minute
- Executes relay commands based on cron expressions
- Records execution with source="schedule"

### Trigger Loop
- Evaluates triggers against latest sensor readings
- Supports conditions: >, <, >=, <=, ==, !=
- Cooldown period to prevent rapid toggling

## Web Dashboard

### URL
`http://<pi-ip>:8000/dashboard`

### Features
- Real-time sensor readings
- Relay toggle controls
- Schedule management
- Trigger management
- Device status monitoring
- Sensor history charts

### API Key for Dashboard
1. Click "Settings" button (gear icon)
2. Enter API key
3. Click Save
4. Key stored in browser localStorage

## Current Hardware Setup

### Devices Configured
1. **SHT20 Sensor** (Address 1): Air temperature + humidity
2. **Soil 7-in-1 Sensor** (Address 3): Moisture, temp, EC, pH, N, P, K
3. **ESP32 #4 Relay Controller** (Address 19): 6 channels (fans, irrigation)
4. **ESP32 #5 Relay Controller** (Address 20): 6 channels (fans)

### Relay Labels
- Fan 1-10: Ventilation control
- Irrigation Pump: Water delivery

## Cloudflare Tunnel Access

### Hostnames
- SSH: `a20MCP-fd32443bc2d3.hydromods.org`
- API: `a20MCP-api-fd32443bc2d3.hydromods.org`

### SSH Access
```bash
ssh pi-tunnel  # Uses ~/.ssh/config alias
# or
ssh -o ProxyCommand="cloudflared access ssh --hostname a20MCP-fd32443bc2d3.hydromods.org" pi@localhost
```

## Service Management

### Systemd Service
```bash
# Status
sudo systemctl status a64-iot-controller

# Restart
sudo systemctl restart a64-iot-controller

# Logs
sudo journalctl -u a64-iot-controller -f

# Enable on boot
sudo systemctl enable a64-iot-controller
```

### Service File Location
`/etc/systemd/system/a64-iot-controller.service`

## Common Tasks

### Add a New Sensor
1. Identify Modbus address and register map
2. Create/update model mapping in `models/` directory
3. Use discovery endpoint or manually add via API:
```bash
curl -X POST http://localhost:8000/api/devices \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "gateway_id": "gateway-uuid",
    "modbus_address": 5,
    "device_type": "sensor",
    "model": "SHT20",
    "name": "New Sensor"
  }'
```

### Control a Relay
```bash
# Turn ON
curl -X PUT http://localhost:8000/api/relays/{channel_id} \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"state": true}'

# Turn OFF
curl -X PUT http://localhost:8000/api/relays/{channel_id} \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"state": false}'
```

### Create a Schedule
```bash
curl -X POST http://localhost:8000/api/schedules \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "name": "Morning Irrigation",
    "channel_id": "relay-channel-uuid",
    "action": "on",
    "cron_expression": "0 6 * * *",
    "enabled": true
  }'
```

### Create a Trigger
```bash
curl -X POST http://localhost:8000/api/triggers \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "name": "High Temp Fan",
    "sensor_channel_id": "temp-channel-uuid",
    "relay_channel_id": "fan-channel-uuid",
    "condition": ">",
    "threshold": 30.0,
    "action": "on",
    "cooldown_seconds": 300,
    "enabled": true
  }'
```

## Integration with A64Core Platform

### How It Works
1. A64Core Platform frontend (BlockAutomationTab) calls `/api/v1/farm/iot-proxy`
2. Backend proxy forwards request to this IoT controller
3. Controller responds with sensor/relay data in expected format
4. Frontend displays data and allows relay control

### Configuration in A64Core
Each block in A64Core can have an IoT controller configured:
```json
{
  "iotController": {
    "address": "a20MCP-api-fd32443bc2d3.hydromods.org",
    "port": 443,
    "enabled": true,
    "apiKey": "fmeh-Wb5-fLUMIV9vBQTWu8HGwd0JMRTF0t-E9oXvM0"
  }
}
```

## Debugging

### Check Service Status
```bash
sudo systemctl status a64-iot-controller
```

### View Live Logs
```bash
sudo journalctl -u a64-iot-controller -f
```

### Test API
```bash
# Health check
curl http://localhost:8000/api/health

# Get readings
curl http://localhost:8000/api/readings

# Test relay (requires API key)
curl -X PUT http://localhost:8000/api/relays/{id} \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"state": true}'
```

### Check Database
```bash
sqlite3 data/controller.db
.tables
SELECT * FROM devices;
SELECT * FROM readings ORDER BY timestamp DESC LIMIT 10;
```

## Known Issues & TODOs

### Current Issues
1. Dashboard Settings modal saves API key to localStorage but may have browser compatibility issues
2. Relay state "via recovery" shown after service restart (expected behavior)

### Future Improvements
- WebSocket for real-time updates
- Multi-gateway support improvements
- Backup/restore functionality
- Alert notifications (email, push)

## Recent Changes (January 2026)

1. **Added /api/a64core endpoint** - Aggregated data format for A64Core Platform integration
2. **Added controller identity settings** - `CONTROLLER_ID` and `CONTROLLER_NAME` in config
3. **Fixed polling loops** - Moved background task creation to correct startup method
4. **Added relay status updates** - Update device online status after successful relay commands
5. **Added dashboard history charts** - Click sensor cards to view historical data
6. **Added Settings modal** - API key configuration in web dashboard
