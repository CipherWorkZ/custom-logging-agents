# NPM Logging Agent

A lightweight Python agent that monitors **Nginx Proxy Manager (NPM) logs**, ships them to **Graylog**, and provides **tracking IDs (TIDs)** for error sessions until they are resolved.  

This agent helps you **centralize NPM logs**, detect problems quickly, and correlate multiple error events with a single tracking ID for easier troubleshooting.

---

## ✨ Features

- 📡 **Live log monitoring** – Tails NPM access and error logs in real time.  
- 🛰 **Graylog integration** – Sends structured JSON messages to Graylog via Syslog (TCP/UDP).  
- 🆔 **Tracking IDs (TIDs)** – Automatically assigns a unique TID when a proxy host starts experiencing errors.  
- 📊 **Issue summaries** – When the issue resolves, the agent sends a summary log (start time, end time, duration, error count, last error).  
- 🕒 **Timezone support** – Timestamps use your configured timezone.  
- ⚡ **Resilient & lightweight** – Built on `watchdog` for file monitoring.  

---

## 📦 Installation

1. **Clone this repository** (or copy the agent files):  

   ```bash
   git clone https://github.com/CipherWorkZ/custom-logging-agents.git
   cd custom-logging-agents/npm-agent
   ```

2. **Install dependencies**:  

   ```bash
   sudo apt update
   sudo apt install python3 python3-pip -y
   pip3 install watchdog pytz
   ```

3. **Copy files into place**:  

   ```bash
   sudo cp npm_monitor.py /usr/local/bin/npm_monitor.py
   sudo cp npm_monitor.conf /etc/npm_monitor.conf
   sudo cp npm-monitor.service /etc/systemd/system/npm-monitor.service
   sudo chmod +x /usr/local/bin/npm_monitor.py
   ```

---
### 🔄 Auto-Updater

Each agent comes with an **`agent_updater.py`** script and a systemd service to keep it up-to-date.  
The updater checks GitHub for new versions, downloads updates automatically, and restarts the agent if needed.  

#### Setup
1. Copy the updater script:  
   ```bash
   sudo cp agent_updater.py /usr/local/bin/agent_updater.py
   sudo chmod +x /usr/local/bin/agent_updater.py
   ```

2. Copy the config file to `/etc/`:  
   ```bash
   sudo cp agent_updater.conf /etc/agent_updater.conf
   ```

3. Create a log file:  
   ```bash
   sudo touch /var/log/agent_updater.log
   sudo chown nobody:nogroup /var/log/agent_updater.log
   ```

4. Add systemd service: `/etc/systemd/system/agent-updater.service`  
   ```ini
   [Unit]
   Description=Agent Updater Service
   After=network.target

   [Service]
   ExecStart=/usr/bin/python3 /usr/local/bin/agent_updater.py
   Restart=always
   RestartSec=10
   User=nobody
   Group=nogroup
   StandardOutput=append:/var/log/agent_updater.log
   StandardError=append:/var/log/agent_updater.log

   [Install]
   WantedBy=multi-user.target
   ```

5. Enable & start:  
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable agent-updater
   sudo systemctl start agent-updater
   ```

📌 Once set up, the updater runs in the background and ensures your agent always stays current.


---

## ⚙️ Configuration

Edit `/etc/npm_monitor.conf` to match your environment:

```ini
[graylog]
host = 192.168.1.214     # Graylog server
port = 5140              # Syslog input port
protocol = tcp           # tcp or udp
source = NPM-Monitor     # Source name in Graylog

[general]
log_dir = /home/docker/npm/data/logs   # NPM logs directory
timezone = America/New_York            # Local timezone
```

---

## ▶️ Usage

Enable and start the systemd service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable npm-monitor
sudo systemctl start npm-monitor
```

Check logs:

```bash
journalctl -u npm-monitor -f
```

---

## 🔍 Graylog Integration

1. In Graylog, create a **Syslog TCP input** on the same port as configured (`5140`).  
2. (Optional) Create a **Stream** with a rule:  

   ```
   Field: message
   Condition: contains
   Value: NPM-Monitor
   ```

   → This isolates logs from the NPM agent into their own stream.

---

## 📜 Example Log Events

### Normal log line
```json
{
  "timestamp": "2025-09-16T13:12:45-04:00",
  "source": "NPM-Monitor",
  "log_type": "access",
  "proxy_host": "12",
  "file": "proxy-host-12_access.log",
  "message": "GET /index.html 200"
}
```

### New issue detected
```json
{
  "timestamp": "2025-09-16T13:15:10-04:00",
  "source": "NPM-Monitor",
  "log_type": "error",
  "proxy_host": "22",
  "file": "proxy-host-22_error.log",
  "message": "upstream connection failed",
  "tid": "c73f9f3c-9a65-4c3a-81e1-1e1f99c18d2a",
  "event": "issue_start"
}
```

### Issue summary (resolved)
```json
{
  "timestamp": "2025-09-16T13:20:12-04:00",
  "source": "NPM-Monitor",
  "proxy_host": "22",
  "tid": "c73f9f3c-9a65-4c3a-81e1-1e1f99c18d2a",
  "event": "issue_summary",
  "start_time": "2025-09-16T13:15:10-04:00",
  "end_time": "2025-09-16T13:20:12-04:00",
  "duration_sec": 302,
  "error_count": 15,
  "last_error": "upstream connection failed"
}
```

---

## 🛠 Troubleshooting

- Make sure your Graylog Syslog input is listening on the right **IP/port/protocol**.  
- Check `journalctl -u npm-monitor -f` for errors.  
- Verify the `log_dir` path matches your **NPM container volume** (`~/npm/data/logs`).  

---

## 📜 License

MIT License – free to use and modify.  
