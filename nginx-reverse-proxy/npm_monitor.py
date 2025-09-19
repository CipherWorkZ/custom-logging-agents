#!/usr/bin/env python3
import os, time, socket, json, datetime, pytz, configparser, logging, sys, uuid
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

CONFIG_FILE = "/etc/npm_monitor.conf"
LOG_FILE = "/var/log/npm_monitor.log"3
AGENT_VERSION = "1.0.1"


# --- Setup logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)]
)

# --- Config ---
config = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
config.read(CONFIG_FILE)

GRAYLOG_HOST = config.get("graylog", "host", fallback="127.0.0.1")
GRAYLOG_PORT = config.getint("graylog", "port", fallback=5140)
PROTOCOL = config.get("graylog", "protocol", fallback="tcp").lower()
SOURCE_NAME = config.get("graylog", "source", fallback="NPM-Monitor")
LOG_DIR = config.get("general", "log_dir", fallback="/var/log/npm")
TIMEZONE = config.get("general", "timezone", fallback="UTC")

try:
    tz = pytz.timezone(TIMEZONE)
except Exception:
    tz = pytz.UTC

# --- State tracking ---
active_issues = {}  # proxy_host -> {"tid": str, "start": dt, "last_seen": dt, "count": int, "last_error": str}

# --- Syslog Sender ---
def send_to_graylog(message: dict):
    try:
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        pri = "<134>"
        syslog_msg = f"{pri}{timestamp} {SOURCE_NAME} npm-monitor: {json.dumps(message)}\n"

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM if PROTOCOL == "tcp" else socket.SOCK_DGRAM)
        if PROTOCOL == "tcp":
            sock.connect((GRAYLOG_HOST, GRAYLOG_PORT))
            sock.sendall(syslog_msg.encode("utf-8"))
        else:
            sock.sendto(syslog_msg.encode("utf-8"), (GRAYLOG_HOST, GRAYLOG_PORT))
        sock.close()
    except Exception as e:
        logging.error(f"Error sending log: {e}")

# --- Problem Detection ---
def is_problem(log_type, line):
    if log_type == "error":
        return True
    if log_type == "access" and " 5" in line[:5]:  # crude HTTP 5xx detection
        return True
    return False

# --- Watchdog Handler ---
class LogHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith(".log"):
            return

        log_type = "access" if "access" in event.src_path else "error"
        proxy_host = None
        if "proxy-host" in event.src_path:
            try:
                proxy_host = event.src_path.split("proxy-host-")[1].split("_")[0]
            except Exception:
                proxy_host = "unknown"

        try:
            with open(event.src_path, "rb") as f:
                f.seek(0, os.SEEK_END)
                fsize = f.tell()
                f.seek(max(fsize - 2048, 0), os.SEEK_SET)
                lines = f.read().decode(errors="ignore").splitlines()[-5:]
                for line in lines:
                    msg = {
                        "timestamp": datetime.datetime.now(tz).isoformat(),
                        "source": SOURCE_NAME,
                        "log_type": log_type,
                        "proxy_host": proxy_host,
                        "file": os.path.basename(event.src_path),
                        "message": line.strip()
                    }

                    if is_problem(log_type, line):
                        issue = active_issues.get(proxy_host)
                        if not issue:
                            tid = str(uuid.uuid4())
                            active_issues[proxy_host] = {
                                "tid": tid,
                                "start": datetime.datetime.now(tz),
                                "last_seen": datetime.datetime.now(tz),
                                "count": 1,
                                "last_error": line.strip()
                            }
                            logging.info(f"New issue detected proxy={proxy_host}, TID={tid}")
                            msg["tid"] = tid
                            msg["event"] = "issue_start"
                        else:
                            issue["last_seen"] = datetime.datetime.now(tz)
                            issue["count"] += 1
                            issue["last_error"] = line.strip()
                            msg["tid"] = issue["tid"]
                    else:
                        msg["tid"] = active_issues.get(proxy_host, {}).get("tid")

                    send_to_graylog(msg)

        except Exception as e:
            logging.error(f"Failed to read {event.src_path}: {e}")

# --- Issue Cleanup ---
def cleanup_issues(timeout=60):
    now = datetime.datetime.now(tz)
    expired = [ph for ph, issue in active_issues.items() if (now - issue["last_seen"]).total_seconds() > timeout]
    for ph in expired:
        issue = active_issues[ph]
        summary = {
            "timestamp": now.isoformat(),
            "source": SOURCE_NAME,
            "proxy_host": ph,
            "tid": issue["tid"],
            "event": "issue_summary",
            "start_time": issue["start"].isoformat(),
            "end_time": issue["last_seen"].isoformat(),
            "duration_sec": (issue["last_seen"] - issue["start"]).total_seconds(),
            "error_count": issue["count"],
            "last_error": issue["last_error"]
        }
        logging.info(f"Issue resolved proxy={ph}, TID={issue['tid']}, duration={summary['duration_sec']}s")
        send_to_graylog(summary)
        del active_issues[ph]

# --- Main ---
if __name__ == "__main__":
    logging.info(f"Starting NPM Monitor watching {LOG_DIR}, sending to {GRAYLOG_HOST}:{GRAYLOG_PORT}")
    event_handler = LogHandler()
    observer = Observer()
    observer.schedule(event_handler, LOG_DIR, recursive=False)
    observer.start()
    try:
        while True:
            cleanup_issues()
            time.sleep(5)
    except KeyboardInterrupt:
        observer.stop()
        logging.info("NPM Monitor stopped")
    observer.join()
