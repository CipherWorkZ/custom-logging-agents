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
