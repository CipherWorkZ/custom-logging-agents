#!/usr/bin/env python3
import os, sys, time, configparser, requests, subprocess, logging, re

CONFIG_FILE = "/etc/agent_updater.conf"
LOG_FILE    = "/var/log/agent_updater.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)]
)

# --- Load Config ---
config = configparser.ConfigParser(inline_comment_prefixes=("#",";"))
config.read(CONFIG_FILE)

INTERVAL    = config.getint("general", "check_interval", fallback=3600)
AGENT_NAME  = config.get("agent", "name")
LOCAL_PATH  = config.get("agent", "local_path")
REPO_FOLDER = config.get("agent", "repo_folder")
BASE_URL    = config.get("github", "base_url")

# --- Helpers ---
def read_local_version(path):
    """Extract AGENT_VERSION from local script"""
    try:
        with open(path, "r") as f:
            for line in f:
                match = re.match(r'^\s*AGENT_VERSION\s*=\s*["\'](.+?)["\']', line)
                if match:
                    return match.group(1)
    except FileNotFoundError:
        logging.warning(f"Agent file missing: {path}")
    return None

def get_remote_version():
    """Fetch VERSION file from GitHub"""
    url = f"{BASE_URL}/{REPO_FOLDER}/{AGENT_NAME}.VERSION"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.text.strip()
    except Exception as e:
        logging.error(f"Remote version fetch failed: {e}")
    return None

def update_agent():
    """Download latest agent file and replace"""
    url = f"{BASE_URL}/{REPO_FOLDER}/{AGENT_NAME}.py"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            backup = f"{LOCAL_PATH}.{int(time.time())}.bak"
            if os.path.exists(LOCAL_PATH):
                os.rename(LOCAL_PATH, backup)
            with open(LOCAL_PATH, "wb") as f:
                f.write(r.content)
            logging.info(f"Updated {AGENT_NAME} at {LOCAL_PATH} (backup at {backup})")
            return True
    except Exception as e:
        logging.error(f"Update failed: {e}")
    return False

def restart_service():
    """Restart systemd service"""
    svc = f"{AGENT_NAME.replace('_','-')}.service"
    try:
        subprocess.run(["systemctl", "restart", svc], check=True)
        logging.info(f"Restarted {svc}")
    except Exception as e:
        logging.error(f"Failed restarting {svc}: {e}")

def check_agent():
    local_ver  = read_local_version(LOCAL_PATH)
    remote_ver = get_remote_version()

    if not local_ver:
        logging.warning("No local version found")
        return
    if not remote_ver:
        logging.warning("No remote version found")
        return

    if local_ver != remote_ver:
        logging.info(f"Update available: {local_ver} → {remote_ver}")
        if update_agent():
            restart_service()
            new_ver = read_local_version(LOCAL_PATH)
            if new_ver == remote_ver:
                logging.info(f"Update verified: now running {new_ver}")
            else:
                logging.warning(f"Update verification failed (expected {remote_ver}, got {new_ver})")
    else:
        logging.info(f"{AGENT_NAME} is up-to-date ({local_ver})")

# --- Main Loop ---
if __name__ == "__main__":
    logging.info(f"Starting updater for {AGENT_NAME}")
    while True:
        check_agent()
        time.sleep(INTERVAL)
