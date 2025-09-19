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
