#!/usr/bin/env python3
import psutil
import socket
import json
import time
import datetime
import pytz
import configparser
import logging
import sys
import uuid

CONFIG_FILE = "/etc/ffmpeg_monitor.conf"
LOG_FILE = "/var/log/ffmpeg_monitor.log"

# --- Setup logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

# --- Load Config ---
config = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
config.read(CONFIG_FILE)

GRAYLOG_HOST = config.get("graylog", "host", fallback="127.0.0.1")
GRAYLOG_PORT = config.getint("graylog", "port", fallback=5140)
PROTOCOL = config.get("graylog", "protocol", fallback="tcp").lower()
SOURCE_NAME = config.get("graylog", "source", fallback="FFMPEG-Monitor")

TIMEZONE = config.get("general", "timezone", fallback="UTC")
INTERVAL = config.getint("general", "interval", fallback=5)

# --- Setup Timezone ---
try:
    tz = pytz.timezone(TIMEZONE)
except Exception:
    tz = pytz.UTC

# --- Tracking maps ---
tracking_map = {}   # pid -> tid
stats_map = {}      # tid -> stats accumulator

# --- Logging Functions ---
def send_to_graylog(message: dict):
    try:
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        pri = "<134>"  # Facility=local0, Severity=info
        syslog_msg = f"{pri}{timestamp} {SOURCE_NAME} ffmpeg-monitor: {json.dumps(message)}\n"

        if PROTOCOL == "tcp":
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((GRAYLOG_HOST, GRAYLOG_PORT))
            sock.sendall(syslog_msg.encode("utf-8"))
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(syslog_msg.encode("utf-8"), (GRAYLOG_HOST, GRAYLOG_PORT))

        sock.close()
        logging.debug(f"Sent syslog to Graylog ({PROTOCOL.upper()} {GRAYLOG_HOST}:{GRAYLOG_PORT})")
    except Exception as e:
        logging.error(f"Error sending syslog: {e}")

# --- Metrics Collector ---
def collect_metrics():
    global tracking_map, stats_map

    current_pids = set()
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if proc.info['name'] == "ffmpeg":
            pid = proc.pid
            current_pids.add(pid)

            # Assign new TID if this PID is new
            if pid not in tracking_map:
                tid = str(uuid.uuid4())
                tracking_map[pid] = tid
                stats_map[tid] = {
                    "pid": pid,
                    "command": " ".join(proc.info['cmdline']),
                    "start_time": datetime.datetime.now(tz),
                    "cpu_samples": [],
                    "ram_samples": [],
                    "read_bytes": 0,
                    "write_bytes": 0,
                    "net_sent": 0,
                    "net_recv": 0,
                }
                logging.info(f"New FFmpeg process detected PID={pid}, TID={tid}")

            tid = tracking_map[pid]
            stats = stats_map[tid]

            try:
                cpu = proc.cpu_percent(interval=1)
                mem = proc.memory_info().rss / (1024 * 1024)  # MB
                io = proc.io_counters()
                net = psutil.net_io_counters()

                # Save stats for summary
                stats["cpu_samples"].append(cpu)
                stats["ram_samples"].append(mem)
                stats["read_bytes"] += io.read_bytes
                stats["write_bytes"] += io.write_bytes
                stats["net_sent"] = net.bytes_sent
                stats["net_recv"] = net.bytes_recv

                log = {
                    "timestamp": datetime.datetime.now(tz).isoformat(),
                    "source": SOURCE_NAME,
                    "pid": pid,
                    "tid": tid,
                    "command": stats["command"],
                    "cpu_percent": cpu,
                    "ram_mb": mem,
                    "read_bytes": io.read_bytes,
                    "write_bytes": io.write_bytes,
                    "net_sent_bytes": net.bytes_sent,
                    "net_recv_bytes": net.bytes_recv,
                }

                logging.info(f"TID={tid} PID={pid} CPU={cpu:.1f}% RAM={mem:.1f}MB")
                send_to_graylog(log)

            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logging.warning(f"Process vanished or no access: PID={pid} ({e})")

    # Clean up old PIDs no longer running
    tracked_pids = set(tracking_map.keys())
    dead_pids = tracked_pids - current_pids
    for pid in dead_pids:
        tid = tracking_map[pid]
        stats = stats_map.get(tid, {})
        end_time = datetime.datetime.now(tz)
        duration = (end_time - stats["start_time"]).total_seconds()

        # Build summary log
        if stats:
            summary = {
                "timestamp": end_time.isoformat(),
                "source": SOURCE_NAME,
                "pid": pid,
                "tid": tid,
                "command": stats["command"],
                "event": "summary",
                "start_time": stats["start_time"].isoformat(),
                "end_time": end_time.isoformat(),
                "duration_sec": duration,
                "cpu_avg_percent": sum(stats["cpu_samples"]) / len(stats["cpu_samples"]) if stats["cpu_samples"] else 0,
                "cpu_max_percent": max(stats["cpu_samples"]) if stats["cpu_samples"] else 0,
                "ram_max_mb": max(stats["ram_samples"]) if stats["ram_samples"] else 0,
                "bytes_read_total": stats["read_bytes"],
                "bytes_written_total": stats["write_bytes"],
                "net_sent_total": stats["net_sent"],
                "net_recv_total": stats["net_recv"],
            }
            logging.info(f"FFmpeg PID={pid} (TID={tid}) ended, sending summary")
            send_to_graylog(summary)

        # Remove from maps
        del tracking_map[pid]
        stats_map.pop(tid, None)

# --- Main Loop ---
if __name__ == "__main__":
    logging.info(f"Starting FFmpeg Monitor (interval {INTERVAL}s, Graylog={GRAYLOG_HOST}:{GRAYLOG_PORT}, proto={PROTOCOL})")
    try:
        while True:
            collect_metrics()
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        logging.info("Monitor stopped by user.")
