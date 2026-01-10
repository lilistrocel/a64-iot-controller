/**
 * A64 IoT Controller Dashboard - Alpine.js Application
 */

document.addEventListener('alpine:init', () => {
    // Main dashboard store
    Alpine.store('dashboard', {
        currentTab: 'overview',
        loading: false,
        error: null,
        lastUpdate: null,
        autoRefresh: true,
        refreshInterval: 5000,

        // Data
        status: null,
        health: null,
        readings: [],
        relays: [],
        schedules: [],
        triggers: [],
        devices: [],
        gateways: [],
        relayChannels: [],
        sensorChannels: [],

        // Toast notifications
        toasts: [],

        // Modals
        showScheduleModal: false,
        showTriggerModal: false,
        editingSchedule: null,
        editingTrigger: null,

        // History
        showHistoryModal: false,
        historyChannel: null,
        historyData: [],
        historyStats: null,
        historyHours: '24',
        historyLoading: false,
        historyChart: null,

        // Settings
        showSettingsModal: false,
        apiKeyInput: '',

        // Initialize
        async init() {
            // Load API key from localStorage
            this.apiKeyInput = api.getApiKey() || '';
            await this.refresh();
            this.startAutoRefresh();
        },

        // Refresh all data
        async refresh() {
            this.loading = true;
            this.error = null;

            try {
                const [status, health, readings, relays, schedules, triggers, devices, gateways, relayChannels, sensorChannels] = await Promise.all([
                    api.fetchStatus().catch(() => null),
                    api.fetchHealth().catch(() => null),
                    api.fetchReadings().catch(() => []),
                    api.fetchRelays().catch(() => []),
                    api.fetchSchedules().catch(() => []),
                    api.fetchTriggers().catch(() => []),
                    api.fetchDevices().catch(() => []),
                    api.fetchGateways().catch(() => []),
                    api.fetchRelayChannels().catch(() => []),
                    api.fetchSensorChannels().catch(() => [])
                ]);

                this.status = status;
                this.health = health;
                this.readings = readings;
                this.relays = relays;
                this.schedules = schedules;
                this.triggers = triggers;
                this.devices = devices;
                this.gateways = gateways;
                this.relayChannels = relayChannels;
                this.sensorChannels = sensorChannels;
                this.lastUpdate = new Date();
            } catch (e) {
                this.error = e.message;
                this.showToast('Error refreshing data: ' + e.message, 'error');
            }

            this.loading = false;
        },

        // Auto-refresh
        startAutoRefresh() {
            setInterval(() => {
                if (this.autoRefresh) {
                    this.refresh();
                }
            }, this.refreshInterval);
        },

        // Toggle relay
        async toggleRelay(channelId, currentState) {
            try {
                await api.controlRelay(channelId, !currentState);
                this.showToast(`Relay ${currentState ? 'OFF' : 'ON'}`, 'success');
                await this.refresh();
            } catch (e) {
                this.showToast('Error: ' + e.message, 'error');
            }
        },

        // Schedule CRUD
        openScheduleModal(schedule = null) {
            this.editingSchedule = schedule ? { ...schedule } : {
                channel_id: '',
                name: '',
                time_on: '08:00',
                time_off: '18:00',
                days_of_week: '[0,1,2,3,4,5,6]',
                enabled: true
            };
            this.showScheduleModal = true;
        },

        async saveSchedule() {
            try {
                const data = { ...this.editingSchedule };
                if (data.id) {
                    await api.updateSchedule(data.id, data);
                    this.showToast('Schedule updated', 'success');
                } else {
                    await api.createSchedule(data);
                    this.showToast('Schedule created', 'success');
                }
                this.showScheduleModal = false;
                await this.refresh();
            } catch (e) {
                this.showToast('Error: ' + e.message, 'error');
            }
        },

        async deleteSchedule(scheduleId) {
            if (!confirm('Delete this schedule?')) return;
            try {
                await api.deleteSchedule(scheduleId);
                this.showToast('Schedule deleted', 'success');
                await this.refresh();
            } catch (e) {
                this.showToast('Error: ' + e.message, 'error');
            }
        },

        async toggleSchedule(schedule) {
            try {
                if (schedule.enabled) {
                    await api.disableSchedule(schedule.id);
                } else {
                    await api.enableSchedule(schedule.id);
                }
                await this.refresh();
            } catch (e) {
                this.showToast('Error: ' + e.message, 'error');
            }
        },

        // Trigger CRUD
        openTriggerModal(trigger = null) {
            this.editingTrigger = trigger ? { ...trigger } : {
                name: '',
                source_channel_id: '',
                target_channel_id: '',
                operator: '>',
                threshold: 0,
                action: 'on',
                cooldown: 300,
                enabled: true
            };
            this.showTriggerModal = true;
        },

        async saveTrigger() {
            try {
                const data = { ...this.editingTrigger };
                if (data.id) {
                    await api.updateTrigger(data.id, data);
                    this.showToast('Trigger updated', 'success');
                } else {
                    await api.createTrigger(data);
                    this.showToast('Trigger created', 'success');
                }
                this.showTriggerModal = false;
                await this.refresh();
            } catch (e) {
                this.showToast('Error: ' + e.message, 'error');
            }
        },

        async deleteTrigger(triggerId) {
            if (!confirm('Delete this trigger?')) return;
            try {
                await api.deleteTrigger(triggerId);
                this.showToast('Trigger deleted', 'success');
                await this.refresh();
            } catch (e) {
                this.showToast('Error: ' + e.message, 'error');
            }
        },

        async toggleTrigger(trigger) {
            try {
                if (trigger.enabled) {
                    await api.disableTrigger(trigger.id);
                } else {
                    await api.enableTrigger(trigger.id);
                }
                await this.refresh();
            } catch (e) {
                this.showToast('Error: ' + e.message, 'error');
            }
        },

        // History
        async showHistory(reading) {
            this.historyChannel = reading;
            this.showHistoryModal = true;
            await this.loadHistory();
        },

        closeHistory() {
            this.showHistoryModal = false;
            if (this.historyChart) {
                this.historyChart.destroy();
                this.historyChart = null;
            }
        },

        async loadHistory() {
            if (!this.historyChannel) return;

            this.historyLoading = true;

            try {
                const [readings, stats] = await Promise.all([
                    api.fetchChannelReadings(this.historyChannel.channel_id, this.historyHours),
                    api.fetchChannelStats(this.historyChannel.channel_id, this.historyHours)
                ]);

                this.historyData = readings;
                this.historyStats = stats;

                // Render chart after a small delay to ensure canvas is visible
                setTimeout(() => this.renderChart(), 100);
            } catch (e) {
                this.showToast('Error loading history: ' + e.message, 'error');
            }

            this.historyLoading = false;
        },

        renderChart() {
            const canvas = document.getElementById('historyChart');
            if (!canvas || !this.historyData.length) return;

            // Destroy existing chart
            if (this.historyChart) {
                this.historyChart.destroy();
            }

            const ctx = canvas.getContext('2d');
            const labels = this.historyData.map(d => new Date(d.timestamp).toLocaleString());
            const data = this.historyData.map(d => d.value);

            this.historyChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: `${this.historyChannel.channel_name} (${this.historyChannel.unit || ''})`,
                        data: data,
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: this.historyData.length > 100 ? 0 : 3,
                        pointHoverRadius: 5
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top'
                        },
                        tooltip: {
                            callbacks: {
                                label: (context) => {
                                    return `${context.parsed.y.toFixed(2)} ${this.historyChannel.unit || ''}`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            display: true,
                            title: {
                                display: true,
                                text: 'Time'
                            },
                            ticks: {
                                maxRotation: 45,
                                maxTicksLimit: 10
                            }
                        },
                        y: {
                            display: true,
                            title: {
                                display: true,
                                text: this.historyChannel.unit || 'Value'
                            }
                        }
                    }
                }
            });
        },

        // Settings
        saveApiKey() {
            api.setApiKey(this.apiKeyInput);
            this.showSettingsModal = false;
            this.showToast('API key saved', 'success');
        },

        // Toast notifications
        showToast(message, type = 'info') {
            const id = Date.now();
            this.toasts.push({ id, message, type });
            setTimeout(() => {
                this.toasts = this.toasts.filter(t => t.id !== id);
            }, 3000);
        },

        // Helpers
        formatTime(timestamp) {
            if (!timestamp) return '-';
            return new Date(timestamp).toLocaleTimeString();
        },

        formatDate(timestamp) {
            if (!timestamp) return '-';
            return new Date(timestamp).toLocaleString();
        },

        getReadingValue(channelName) {
            const reading = this.readings.find(r => r.channel_name === channelName);
            return reading ? `${reading.value.toFixed(1)} ${reading.unit || ''}` : '-';
        },

        getRelayState(channelId) {
            const relay = this.relays.find(r => r.channel_id === channelId);
            return relay ? relay.state : false;
        },

        getDaysText(daysJson) {
            try {
                const days = JSON.parse(daysJson);
                const names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
                if (days.length === 7) return 'Every day';
                if (days.length === 5 && !days.includes(5) && !days.includes(6)) return 'Weekdays';
                if (days.length === 2 && days.includes(5) && days.includes(6)) return 'Weekends';
                return days.map(d => names[d]).join(', ');
            } catch {
                return 'Every day';
            }
        },

        getChannelName(channelId) {
            const all = [...this.relayChannels, ...this.sensorChannels];
            const ch = all.find(c => c.id === channelId);
            return ch ? ch.name : channelId;
        }
    });
});

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    Alpine.store('dashboard').init();
});
