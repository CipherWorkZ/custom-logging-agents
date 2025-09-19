# custom-logging-agents

A collection of lightweight Python agents and systemd services for **custom log collection** and forwarding to **Graylog**.  

Each agent runs independently and is designed to monitor or tail a specific application/service, enrich logs with structured JSON (and tracking IDs when useful), and ship them directly into your logging pipeline.  

As of **v1.0.1**, each logging agent now comes bundled with its own **self-updating agent** – no extra configuration needed.  
The updater checks GitHub for new versions, pulls updates automatically, and restarts the service seamlessly.  

---

## 📑 Table of Contents

1. [FFmpeg Agent](./ffmpeg)  
   - Tracks active FFmpeg transcode processes  
   - Reports CPU, RAM, I/O, and network usage  
   - Assigns tracking IDs (TIDs) per process  
   - Generates per-session summaries when jobs complete  
   - Bundled updater ensures you’re always on the latest version
   - NEW FEATURE issues tracking, track and send issues and error log aswell as a issues id 

2. [Nginx Proxy Manager Agent](./nginx-reverse-proxy)  
   - Tails NPM access/error logs in real time  
   - Streams live log lines into Graylog  
   - Creates tracking IDs (TIDs) for ongoing issues until resolved  
   - Bundled updater ensures you’re always on the latest version  

---

## 📦 Structure

```
custom-logging-agents/
├── ffmpeg/              # FFmpeg monitoring agent
│   ├── ffmpeg_monitor.py
│   ├── ffmpeg_monitor.conf
│   ├── ffmpeg_monitor.service
│   ├── agent_updater.py
│   ├── ffmpeg_monitor.VERSION
│   ├── agent_updater.conf
│   └── README.md
│
├── nginx-reverse-proxy/ # Nginx Proxy Manager log agent
│   ├── npm_monitor.py
│   ├── npm_monitor.conf
│   ├── npm_monitor.service
│   ├── agent_updater.py
│   ├── npm_monitor.VERSION
│   ├── aagent_updater.conf
│   └── README.md
├── update_agent/ # Generic updater framework
│ ├── agent_updater.py
│ ├── agent-updater.service
│ ├── agent_updater.conf
│ ├── agent_updater.log
│ └── README.md
│
└── README.md # Main index (this file)         # Main index (this file)
```

---

## 🚀 How to Use

1. Choose the agent you want from the [Table of Contents](#-table-of-contents).  
2. Enter its folder.  
3. Follow the **README.md** inside that folder for setup instructions.  

⚡ **No need to configure updates manually** – each agent ships with an `agent_updater.py` script and systemd unit that will keep it up-to-date automatically.
