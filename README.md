# custom-logging-agents

A collection of lightweight Python agents and systemd services for **custom log collection** and forwarding to **Graylog**.  

Each agent runs independently and is designed to monitor or tail a specific application/service, enrich logs with structured JSON (and tracking IDs when useful), and ship them directly into your logging pipeline.  

---

## 📑 Table of Contents

1. [FFmpeg Agent](./ffmpeg)  
   - Tracks active FFmpeg transcode processes  
   - Reports CPU, RAM, I/O, and network usage  
   - Assigns tracking IDs (TIDs) per process  
   - Generates per-session summaries when jobs complete  

2. [Nginx Proxy Manager Agent](./nginx-reverse-proxy)  
   - Tails NPM access/error logs in real time  
   - Streams live log lines into Graylog  
   - Creates tracking IDs (TIDs) for ongoing issues until resolved  

---

## 📦 Structure

```
custom-logging-agents/
├── ffmpeg/              # FFmpeg monitoring agent
│   ├── ffmpeg_monitor.py
│   ├── ffmpeg_monitor.conf
│   ├── ffmpeg_monitor.service
│   └── README.md
│
├── nginx-reverse-proxy/ # Nginx Proxy Manager log agent
│   ├── npm_monitor.py
│   ├── npm_monitor.conf
│   ├── npm_monitor.service
│   └── README.md
│
└── README.md            # Main index (this file)
```

---

## 🚀 How to Use

1. Choose the agent you want from the [Table of Contents](#-table-of-contents).  
2. Enter its folder.  
3. Follow the **README.md** inside that folder for setup instructions.  
