/**
 * API Client for A64 IoT Controller
 */

const API_BASE = '/api';

// Get API key from localStorage if set
function getApiKey() {
    return localStorage.getItem('apiKey') || '';
}

function setApiKey(key) {
    localStorage.setItem('apiKey', key);
}

// Common fetch wrapper
async function apiFetch(endpoint, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };

    const apiKey = getApiKey();
    if (apiKey) {
        headers['X-API-Key'] = apiKey;
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || `HTTP ${response.status}`);
    }

    // Handle 204 No Content
    if (response.status === 204) {
        return null;
    }

    return response.json();
}

// Status & Health
async function fetchStatus() {
    return apiFetch('/status');
}

async function fetchHealth() {
    return apiFetch('/health');
}

// Readings
async function fetchReadings() {
    return apiFetch('/readings');
}

async function fetchChannelReadings(channelId, hours = 24) {
    return apiFetch(`/readings/${channelId}?hours=${hours}`);
}

async function fetchChannelStats(channelId, hours = 24) {
    return apiFetch(`/readings/${channelId}/stats?hours=${hours}`);
}

// Relays
async function fetchRelays() {
    return apiFetch('/relays');
}

async function fetchRelayState(channelId) {
    return apiFetch(`/relays/${channelId}`);
}

async function controlRelay(channelId, state) {
    return apiFetch(`/relays/${channelId}`, {
        method: 'PUT',
        body: JSON.stringify({ state })
    });
}

// Schedules
async function fetchSchedules() {
    return apiFetch('/schedules');
}

async function fetchActiveSchedules() {
    return apiFetch('/schedules/active');
}

async function createSchedule(data) {
    return apiFetch('/schedules', {
        method: 'POST',
        body: JSON.stringify(data)
    });
}

async function updateSchedule(scheduleId, data) {
    return apiFetch(`/schedules/${scheduleId}`, {
        method: 'PUT',
        body: JSON.stringify(data)
    });
}

async function deleteSchedule(scheduleId) {
    return apiFetch(`/schedules/${scheduleId}`, {
        method: 'DELETE'
    });
}

async function enableSchedule(scheduleId) {
    return apiFetch(`/schedules/${scheduleId}/enable`, {
        method: 'POST'
    });
}

async function disableSchedule(scheduleId) {
    return apiFetch(`/schedules/${scheduleId}/disable`, {
        method: 'POST'
    });
}

// Triggers
async function fetchTriggers() {
    return apiFetch('/triggers');
}

async function fetchActiveTriggers() {
    return apiFetch('/triggers/active');
}

async function createTrigger(data) {
    return apiFetch('/triggers', {
        method: 'POST',
        body: JSON.stringify(data)
    });
}

async function updateTrigger(triggerId, data) {
    return apiFetch(`/triggers/${triggerId}`, {
        method: 'PUT',
        body: JSON.stringify(data)
    });
}

async function deleteTrigger(triggerId) {
    return apiFetch(`/triggers/${triggerId}`, {
        method: 'DELETE'
    });
}

async function enableTrigger(triggerId) {
    return apiFetch(`/triggers/${triggerId}/enable`, {
        method: 'POST'
    });
}

async function disableTrigger(triggerId) {
    return apiFetch(`/triggers/${triggerId}/disable`, {
        method: 'POST'
    });
}

// Devices
async function fetchDevices() {
    return apiFetch('/devices');
}

async function fetchDevice(deviceId) {
    return apiFetch(`/devices/${deviceId}`);
}

// Gateways
async function fetchGateways() {
    return apiFetch('/gateways');
}

// Channels
async function fetchChannels() {
    return apiFetch('/channels');
}

async function fetchRelayChannels() {
    return apiFetch('/channels/relays');
}

async function fetchSensorChannels() {
    return apiFetch('/channels/sensors');
}

// Export for use
window.api = {
    getApiKey,
    setApiKey,
    fetchStatus,
    fetchHealth,
    fetchReadings,
    fetchChannelReadings,
    fetchChannelStats,
    fetchRelays,
    fetchRelayState,
    controlRelay,
    fetchSchedules,
    fetchActiveSchedules,
    createSchedule,
    updateSchedule,
    deleteSchedule,
    enableSchedule,
    disableSchedule,
    fetchTriggers,
    fetchActiveTriggers,
    createTrigger,
    updateTrigger,
    deleteTrigger,
    enableTrigger,
    disableTrigger,
    fetchDevices,
    fetchDevice,
    fetchGateways,
    fetchChannels,
    fetchRelayChannels,
    fetchSensorChannels
};
