# 🎬 FFmpeg Logging Agent

The **FFmpeg Logging Agent** is a lightweight Python service that monitors active FFmpeg transcoding processes and streams structured logs to **Graylog** (or any syslog-compatible log system).  

It tracks CPU, RAM, disk I/O, and network usage for each FFmpeg process, assigns a **unique tracking ID (TID)** to group metrics per transcode session, and generates both **real-time metrics logs** and a **summary report** when each process ends.  

---

## ✨ Features
- Detects and monitors **FFmpeg processes** automatically  
- Assigns a **Tracking ID (TID)** to each new session  
- Logs include:
  - PID and full FFmpeg command  
  - CPU usage (avg/max)  
  - RAM usage (max)  
  - Disk I/O (bytes read/written)  
  - Network I/O (system counters or relative deltas)  
- Generates **summary logs** when a process ends, with duration and aggregated stats  
- Configurable via simple `.conf` file  
- Runs as a **systemd service**  
- **Bundled updater agent** automatically keeps this service up-to-date from GitHub  
- **Modular extensions** for stderr monitoring, GPU monitoring, and issue tracking  

---

## ⚙️ Configuration

Config file: `/etc/ffmpeg_monitor.conf`

```ini
[graylog]
host = 192.168.1.214
port = 5140
protocol = tcp
source = FFMPEG-Monitor

[general]
timezone = America/New_York
interval = 5

[modules]
stderr_monitor = true
gpu_monitor = true
issue_tracker = true

[gpu]
vendor = nvidia
interval = 10
```

### Sections explained
- **[graylog]** → Connection settings for Graylog/syslog  
- **[general]**  
  - `timezone` → Timezone for timestamps  
  - `interval` → Seconds between metric collection  
- **[modules]**  
  - `stderr_monitor` → Capture FFmpeg stderr output (subtitles, resolution changes, playback issues) and forward to logs  
  - `gpu_monitor` → Enable GPU usage metrics (vendor-specific)  
  - `issue_tracker` → Automatically detect and group playback issues under an **Issue ID (IID)** with compiled logs  
- **[gpu]**  
  - `vendor` → GPU vendor (`nvidia`, `amd`, `intel`)  
  - `interval` → How often to poll GPU stats (seconds)  

---

## 🚀 Installation

1. Copy the script:  
   ```bash
   sudo cp ffmpeg_monitor.py /usr/local/bin/ffmpeg_monitor.py
   sudo chmod +x /usr/local/bin/ffmpeg_monitor.py
   ```

2. Create config file:  
   ```bash
   sudo nano /etc/ffmpeg_monitor.conf
   ```

3. Create log file:  
   ```bash
   sudo touch /var/log/ffmpeg_monitor.log
   sudo chown nobody:nogroup /var/log/ffmpeg_monitor.log
   ```

4. Add systemd service: `/etc/systemd/system/ffmpeg-monitor.service`  
   ```ini
   [Unit]
   Description=FFmpeg Transcode Monitor
   After=network.target

   [Service]
   ExecStart=/usr/bin/python3 /usr/local/bin/ffmpeg_monitor.py
   Restart=always
   User=nobody
   Group=nogroup

   [Install]
   WantedBy=multi-user.target
   ```

5. Enable & start:  
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable ffmpeg-monitor
   sudo systemctl start ffmpeg-monitor
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

## 📊 Example Logs

### Real-time metric log
```json
{
  "timestamp": "2025-09-16T10:45:01-04:00",
  "source": "FFMPEG-Monitor",
  "pid": 44571,
  "tid": "32763b88-0598-4390-a561-859585f980da",
  "command": "ffmpeg -i input.mkv -c:v libx264 -f hls output.m3u8",
  "cpu_percent": 72.5,
  "ram_mb": 534.2,
  "read_bytes": 20971520,
  "write_bytes": 10485760,
  "net_sent_bytes": 1234567,
  "net_recv_bytes": 987654
}
```

### Summary log
```json
{
  "event": "summary",
  "tid": "32763b88-0598-4390-a561-859585f980da",
  "pid": 44571,
  "command": "ffmpeg -i input.mkv -c:v libx264 -f hls output.m3u8",
  "start_time": "2025-09-16T10:40:24-04:00",
  "end_time": "2025-09-16T11:05:22-04:00",
  "duration_sec": 1500,
  "cpu_avg_percent": 72.3,
  "cpu_max_percent": 99.1,
  "ram_max_mb": 522.6,
  "bytes_read_total": 104857600,
  "bytes_written_total": 524288000,
  "net_sent_total": 130340,
  "net_recv_total": 89010
}
```

### Issue log (example)
```json
{
  "event": "issue",
  "iid": "d45c3b92-1180-4c59-b8ac-1a7e21d56c99",
  "tid": "32763b88-0598-4390-a561-859585f980da",
  "pid": 44571,
  "type": "subtitle_load_failure",
  "details": "Subtitle stream failed to load at 00:12:34",
  "timestamp": "2025-09-16T10:50:12-04:00"
}
```

---

## 🔎 Using in Graylog

1. Create a **Syslog TCP input** (or Raw/Plaintext TCP if you prefer pure JSON).  
2. Add a **Stream** with a rule:
   - Field: `message`  
   - Contains: `ffmpeg-monitor:`  
3. (Optional) Add a **JSON extractor** on the `message` field to parse `tid`, `cpu_percent`, `ram_mb`, `iid`, etc.  
4. Build dashboards showing CPU/RAM per TID, GPU usage, or number of issues detected.  

---

## 📌 Notes
- Network I/O values are currently **system-wide**, not per-process. They can be adjusted to relative deltas if needed.  
- The agent is meant to be **extensible**: you can reuse the same pattern for other apps (nginx, postgres, etc.).  
- With the built-in updater and new modules, you can deploy once and get continuous improvements.  
