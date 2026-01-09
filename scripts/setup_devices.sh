#!/bin/bash
# Setup devices for Alain Greenhouse 11

API="http://localhost:8000/api"
KEY="X-API-Key: fmeh-Wb5-fLUMIV9vBQTWu8HGwd0JMRTF0t-E9oXvM0"
GW="4cb8e58e-6d75-4ad9-b3a0-ba460c02cad4"

echo "Adding SHT20..."
SHT20=$(curl -s -X POST "$API/devices" -H "Content-Type: application/json" -H "$KEY" -d "{
  \"gateway_id\": \"$GW\",
  \"modbus_address\": 1,
  \"device_type\": \"sensor\",
  \"model\": \"SHT20\",
  \"name\": \"Air Temp/Humidity Sensor\",
  \"category\": \"environment\"
}")
SHT20_ID=$(echo $SHT20 | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "  SHT20 ID: $SHT20_ID"

curl -s -X POST "$API/channels" -H "Content-Type: application/json" -H "$KEY" -d "{\"device_id\": \"$SHT20_ID\", \"channel_num\": 1, \"channel_type\": \"temperature\", \"name\": \"Air Temperature\", \"category\": \"environment\", \"unit\": \"C\"}" > /dev/null
curl -s -X POST "$API/channels" -H "Content-Type: application/json" -H "$KEY" -d "{\"device_id\": \"$SHT20_ID\", \"channel_num\": 2, \"channel_type\": \"humidity\", \"name\": \"Air Humidity\", \"category\": \"environment\", \"unit\": \"%\"}" > /dev/null
echo "  Added 2 channels"

echo "Adding Soil 7-in-1..."
SOIL=$(curl -s -X POST "$API/devices" -H "Content-Type: application/json" -H "$KEY" -d "{
  \"gateway_id\": \"$GW\",
  \"modbus_address\": 3,
  \"device_type\": \"sensor\",
  \"model\": \"Soil-7in1\",
  \"name\": \"Soil NPK Sensor\",
  \"category\": \"soil\"
}")
SOIL_ID=$(echo $SOIL | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "  Soil ID: $SOIL_ID"

curl -s -X POST "$API/channels" -H "Content-Type: application/json" -H "$KEY" -d "{\"device_id\": \"$SOIL_ID\", \"channel_num\": 1, \"channel_type\": \"moisture\", \"name\": \"Soil Moisture\", \"category\": \"soil\", \"unit\": \"%\"}" > /dev/null
curl -s -X POST "$API/channels" -H "Content-Type: application/json" -H "$KEY" -d "{\"device_id\": \"$SOIL_ID\", \"channel_num\": 2, \"channel_type\": \"temperature\", \"name\": \"Soil Temperature\", \"category\": \"soil\", \"unit\": \"C\"}" > /dev/null
curl -s -X POST "$API/channels" -H "Content-Type: application/json" -H "$KEY" -d "{\"device_id\": \"$SOIL_ID\", \"channel_num\": 3, \"channel_type\": \"conductivity\", \"name\": \"Soil EC\", \"category\": \"soil\", \"unit\": \"uS/cm\"}" > /dev/null
curl -s -X POST "$API/channels" -H "Content-Type: application/json" -H "$KEY" -d "{\"device_id\": \"$SOIL_ID\", \"channel_num\": 4, \"channel_type\": \"ph\", \"name\": \"Soil pH\", \"category\": \"soil\", \"unit\": \"pH\"}" > /dev/null
curl -s -X POST "$API/channels" -H "Content-Type: application/json" -H "$KEY" -d "{\"device_id\": \"$SOIL_ID\", \"channel_num\": 5, \"channel_type\": \"nitrogen\", \"name\": \"Nitrogen\", \"category\": \"soil\", \"unit\": \"mg/kg\"}" > /dev/null
curl -s -X POST "$API/channels" -H "Content-Type: application/json" -H "$KEY" -d "{\"device_id\": \"$SOIL_ID\", \"channel_num\": 6, \"channel_type\": \"phosphorus\", \"name\": \"Phosphorus\", \"category\": \"soil\", \"unit\": \"mg/kg\"}" > /dev/null
curl -s -X POST "$API/channels" -H "Content-Type: application/json" -H "$KEY" -d "{\"device_id\": \"$SOIL_ID\", \"channel_num\": 7, \"channel_type\": \"potassium\", \"name\": \"Potassium\", \"category\": \"soil\", \"unit\": \"mg/kg\"}" > /dev/null
echo "  Added 7 channels"

echo "Adding ESP32 #4 (address 19)..."
ESP4=$(curl -s -X POST "$API/devices" -H "Content-Type: application/json" -H "$KEY" -d "{
  \"gateway_id\": \"$GW\",
  \"modbus_address\": 19,
  \"device_type\": \"relay_controller\",
  \"model\": \"ESP32-6CH\",
  \"name\": \"ESP32 #4 Relay Controller\",
  \"category\": \"irrigation\"
}")
ESP4_ID=$(echo $ESP4 | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "  ESP32 #4 ID: $ESP4_ID"

curl -s -X POST "$API/channels" -H "Content-Type: application/json" -H "$KEY" -d "{\"device_id\": \"$ESP4_ID\", \"channel_num\": 0, \"channel_type\": \"relay\", \"name\": \"CH0 (unused)\", \"category\": \"irrigation\"}" > /dev/null
curl -s -X POST "$API/channels" -H "Content-Type: application/json" -H "$KEY" -d "{\"device_id\": \"$ESP4_ID\", \"channel_num\": 1, \"channel_type\": \"relay\", \"name\": \"Fan 10\", \"category\": \"ventilation\"}" > /dev/null
curl -s -X POST "$API/channels" -H "Content-Type: application/json" -H "$KEY" -d "{\"device_id\": \"$ESP4_ID\", \"channel_num\": 2, \"channel_type\": \"relay\", \"name\": \"Irrigation Pump\", \"category\": \"irrigation\"}" > /dev/null
curl -s -X POST "$API/channels" -H "Content-Type: application/json" -H "$KEY" -d "{\"device_id\": \"$ESP4_ID\", \"channel_num\": 3, \"channel_type\": \"relay\", \"name\": \"Fan 7\", \"category\": \"ventilation\"}" > /dev/null
curl -s -X POST "$API/channels" -H "Content-Type: application/json" -H "$KEY" -d "{\"device_id\": \"$ESP4_ID\", \"channel_num\": 4, \"channel_type\": \"relay\", \"name\": \"Fan 9\", \"category\": \"ventilation\"}" > /dev/null
curl -s -X POST "$API/channels" -H "Content-Type: application/json" -H "$KEY" -d "{\"device_id\": \"$ESP4_ID\", \"channel_num\": 5, \"channel_type\": \"relay\", \"name\": \"Fan 8\", \"category\": \"ventilation\"}" > /dev/null
echo "  Added 6 channels"

echo "Adding ESP32 #5 (address 20)..."
ESP5=$(curl -s -X POST "$API/devices" -H "Content-Type: application/json" -H "$KEY" -d "{
  \"gateway_id\": \"$GW\",
  \"modbus_address\": 20,
  \"device_type\": \"relay_controller\",
  \"model\": \"ESP32-6CH\",
  \"name\": \"ESP32 #5 Relay Controller\",
  \"category\": \"irrigation\"
}")
ESP5_ID=$(echo $ESP5 | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "  ESP32 #5 ID: $ESP5_ID"

curl -s -X POST "$API/channels" -H "Content-Type: application/json" -H "$KEY" -d "{\"device_id\": \"$ESP5_ID\", \"channel_num\": 0, \"channel_type\": \"relay\", \"name\": \"Fan 6\", \"category\": \"ventilation\"}" > /dev/null
curl -s -X POST "$API/channels" -H "Content-Type: application/json" -H "$KEY" -d "{\"device_id\": \"$ESP5_ID\", \"channel_num\": 1, \"channel_type\": \"relay\", \"name\": \"Fan 2\", \"category\": \"ventilation\"}" > /dev/null
curl -s -X POST "$API/channels" -H "Content-Type: application/json" -H "$KEY" -d "{\"device_id\": \"$ESP5_ID\", \"channel_num\": 2, \"channel_type\": \"relay\", \"name\": \"Fan 3\", \"category\": \"ventilation\"}" > /dev/null
curl -s -X POST "$API/channels" -H "Content-Type: application/json" -H "$KEY" -d "{\"device_id\": \"$ESP5_ID\", \"channel_num\": 3, \"channel_type\": \"relay\", \"name\": \"Fan 4\", \"category\": \"ventilation\"}" > /dev/null
curl -s -X POST "$API/channels" -H "Content-Type: application/json" -H "$KEY" -d "{\"device_id\": \"$ESP5_ID\", \"channel_num\": 4, \"channel_type\": \"relay\", \"name\": \"Fan 5\", \"category\": \"ventilation\"}" > /dev/null
curl -s -X POST "$API/channels" -H "Content-Type: application/json" -H "$KEY" -d "{\"device_id\": \"$ESP5_ID\", \"channel_num\": 5, \"channel_type\": \"relay\", \"name\": \"Fan 1\", \"category\": \"ventilation\"}" > /dev/null
echo "  Added 6 channels"

echo ""
echo "Setup complete! All 4 devices configured."
