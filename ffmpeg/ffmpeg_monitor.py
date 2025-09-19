#!/usr/bin/env python3
AGENT_VERSION = "1.0.1"
import psutil, socket, json, time, datetime, pytz, configparser, logging, sys, uuid, re, threading
try:
    from pynvml import *
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False

CONFIG_FILE = "/etc/ffmpeg_monitor.conf"
LOG_FILE    = "/var/log/ffmpeg_monitor.log"
AGENT_VERSION = "1.0.0"


# --- Setup logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)]
)

# --- Load Config ---
config = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
config.read(CONFIG_FILE)

GRAYLOG_HOST = config.get("graylog", "host", fallback="127.0.0.1")
GRAYLOG_PORT = config.getint("graylog", "port", fallback=5140)
PROTOCOL     = config.get("graylog", "protocol", fallback="tcp").lower()
SOURCE_NAME  = config.get("graylog", "source", fallback="FFMPEG-Monitor")

TIMEZONE     = config.get("general", "timezone", fallback="UTC")
INTERVAL     = config.getint("general", "interval", fallback=5)

USE_STDERR   = config.getboolean("modules", "stderr_monitor", fallback=False)
USE_GPU      = config.getboolean("modules", "gpu_monitor", fallback=False)
USE_ISSUES   = config.getboolean("modules", "issue_tracker", fallback=True)

GPU_INTERVAL = config.getint("gpu", "interval", fallback=10)

# --- Setup Timezone ---
try: tz = pytz.timezone(TIMEZONE)
except Exception: tz = pytz.UTC

# --- State Maps ---
tracking_map = {}   # pid -> tid
stats_map    = {}   # tid -> stats
issues_map   = {}   # iid -> issue data

# --- Logging Helper ---
def send_to_graylog(message: dict):
    try:
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        pri = "<134>"
        syslog_msg = f"{pri}{timestamp} {SOURCE_NAME} ffmpeg-monitor: {json.dumps(message)}\n"

        if PROTOCOL == "tcp":
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((GRAYLOG_HOST, GRAYLOG_PORT))
            sock.sendall(syslog_msg.encode("utf-8"))
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(syslog_msg.encode("utf-8"), (GRAYLOG_HOST, GRAYLOG_PORT))
        sock.close()
    except Exception as e:
        logging.error(f"Graylog send failed: {e}")

# --- Issue Tracker ---
def start_issue(pid, tid, event_type, line):
    iid = str(uuid.uuid4())
    issues_map[iid] = {
        "iid": iid,
        "pid": pid,
        "tid": tid,
        "start_time": datetime.datetime.now(tz),
        "events": [{
            "timestamp": datetime.datetime.now(tz).isoformat(),
            "type": event_type,
            "log_line": line.strip()
        }]
    }
    logging.info(f"Issue started IID={iid} PID={pid} TID={tid} ({event_type})")
    return iid

def append_issue(iid, event_type, line):
    issues_map[iid]["events"].append({
        "timestamp": datetime.datetime.now(tz).isoformat(),
        "type": event_type,
        "log_line": line.strip()
    })

def finalize_issue(iid):
    issue = issues_map.pop(iid, None)
    if not issue: return
    end_time = datetime.datetime.now(tz)
    issue["end_time"] = end_time.isoformat()
    issue["duration_sec"] = (end_time - issue["start_time"]).total_seconds()
    send_to_graylog({
        "event": "issue_summary",
        "iid": issue["iid"],
        "pid": issue["pid"],
        "tid": issue["tid"],
        "start_time": issue["start_time"].isoformat(),
        "end_time": issue["end_time"],
        "duration_sec": issue["duration_sec"],
        "events": issue["events"]
    })
    logging.info(f"Issue IID={iid} finalized and sent")

# --- stderr Monitor ---
ERROR_PATTERNS = {
    "stutter": [r"buffer underflow", r"frame drop", r"too slow"],
    "subtitles": [r"subtitle", r"Failed to read subtitle", r"codec not found"],
    "resolution_change": [r"Stream .* Video: .* (\d+)x(\d+)"],
    "failure": [r"Connection reset", r"error while decoding", r"Server returned 404"]
}

def parse_stderr_line(line, pid, tid):
    for event_type, pats in ERROR_PATTERNS.items():
        for pat in pats:
            if re.search(pat, line, re.IGNORECASE):
                active_iid = None
                if USE_ISSUES:
                    for iid, issue in issues_map.items():
                        if issue["pid"] == pid and issue["tid"] == tid:
                            active_iid = iid
                            break
                    if not active_iid:
                        active_iid = start_issue(pid, tid, event_type, line)
                    else:
                        append_issue(active_iid, event_type, line)
                send_to_graylog({
                    "timestamp": datetime.datetime.now(tz).isoformat(),
                    "source": SOURCE_NAME,
                    "pid": pid, "tid": tid,
                    "iid": active_iid,
                    "event": event_type,
                    "log_line": line.strip()
                })
                return

def watch_stderr(pid, tid):
    try:
        with open(f"/proc/{pid}/fd/2", "r", errors="ignore") as fd:
            for line in fd:
                parse_stderr_line(line, pid, tid)
    except Exception as e:
        logging.debug(f"stderr monitor stopped PID={pid}: {e}")

def start_stderr_thread(pid, tid):
    t = threading.Thread(target=watch_stderr, args=(pid, tid), daemon=True)
    t.start()

# --- GPU Monitor ---
def gpu_loop():
    if not NVML_AVAILABLE:
        logging.warning("GPU monitor requested but pynvml not installed.")
        return
    try:
        nvmlInit()
        handle = nvmlDeviceGetHandleByIndex(0)
    except Exception as e:
        logging.error(f"GPU init failed: {e}")
        return
    while True:
        try:
            util = nvmlDeviceGetUtilizationRates(handle)
            mem = nvmlDeviceGetMemoryInfo(handle)
            send_to_graylog({
                "timestamp": datetime.datetime.now(tz).isoformat(),
                "source": SOURCE_NAME,
                "event": "gpu_stats",
                "gpu_util_percent": util.gpu,
                "mem_used_mb": mem.used // (1024*1024),
                "mem_total_mb": mem.total // (1024*1024)
            })
        except Exception as e:
            logging.error(f"GPU query error: {e}")
        time.sleep(GPU_INTERVAL)

def start_gpu_thread():
    t = threading.Thread(target=gpu_loop, daemon=True)
    t.start()

# --- Metrics Collector ---
def collect_metrics():
    global tracking_map, stats_map
    current_pids = set()
    for proc in psutil.process_iter(['pid','name','cmdline']):
        if proc.info['name'] == "ffmpeg":
            pid = proc.pid
            current_pids.add(pid)
            if pid not in tracking_map:
                tid = str(uuid.uuid4())
                tracking_map[pid] = tid
                stats_map[tid] = {
                    "pid": pid, "command": " ".join(proc.info['cmdline']),
                    "start_time": datetime.datetime.now(tz),
                    "cpu_samples": [], "ram_samples": [],
                    "last_read_bytes": 0, "last_write_bytes": 0
                }
                logging.info(f"New FFmpeg PID={pid}, TID={tid}")
                if USE_STDERR: start_stderr_thread(pid, tid)

            tid = tracking_map[pid]
            stats = stats_map[tid]
            try:
                cpu = proc.cpu_percent(interval=None)
                mem = proc.memory_info().rss / (1024*1024)
                io  = proc.io_counters()
                stats["cpu_samples"].append(cpu)
                stats["ram_samples"].append(mem)
                stats["last_read_bytes"] = io.read_bytes
                stats["last_write_bytes"] = io.write_bytes
                send_to_graylog({
                    "timestamp": datetime.datetime.now(tz).isoformat(),
                    "source": SOURCE_NAME,
                    "pid": pid, "tid": tid,
                    "command": stats["command"],
                    "cpu_percent": cpu, "ram_mb": mem,
                    "read_bytes": io.read_bytes,
                    "write_bytes": io.write_bytes
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    # Cleanup
    for pid in set(tracking_map.keys()) - current_pids:
        tid = tracking_map.pop(pid)
        stats = stats_map.pop(tid, {})
        end_time = datetime.datetime.now(tz)
        if stats:
            send_to_graylog({
                "timestamp": end_time.isoformat(),
                "source": SOURCE_NAME,
                "pid": pid, "tid": tid,
                "command": stats.get("command"),
                "event": "summary",
                "duration_sec": (end_time - stats["start_time"]).total_seconds(),
                "cpu_avg_percent": sum(stats["cpu_samples"])/len(stats["cpu_samples"]) if stats["cpu_samples"] else 0,
                "cpu_max_percent": max(stats["cpu_samples"]) if stats["cpu_samples"] else 0,
                "ram_max_mb": max(stats["ram_samples"]) if stats["ram_samples"] else 0,
                "bytes_read_total": stats.get("last_read_bytes",0),
                "bytes_written_total": stats.get("last_write_bytes",0)
            })
        # finalize issues for this PID
        for iid, issue in list(issues_map.items()):
            if issue["pid"] == pid and issue["tid"] == tid:
                finalize_issue(iid)

# --- Main ---
if __name__ == "__main__":
    logging.info(f"Starting FFmpeg Monitor interval={INTERVAL}s Graylog={GRAYLOG_HOST}:{GRAYLOG_PORT} proto={PROTOCOL}")
    if USE_GPU: start_gpu_thread()
    try:
        while True:
            collect_metrics()
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        logging.info("Monitor stopped by user.")
