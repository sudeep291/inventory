import os
import multiprocessing

# ⚡ ENTERPRISE STABILITY (Render-Tuned)
bind = "0.0.0.0:" + os.environ.get("PORT", "10000")

# 2 workers is optimal for Render free tier (512MB RAM)
# 4 workers causes OOM-kill silent crashes
workers = 2
worker_class = "gthread"
threads = 4

# Auto-recycle workers every 500 requests to prevent memory bloat
max_requests = 500
max_requests_jitter = 50 # Stagger restarts so never all restart at once

# 120s timeout prevents 502 on slow DB cold-boot
timeout = 120
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
