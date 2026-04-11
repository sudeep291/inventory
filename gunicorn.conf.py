import os
import multiprocessing

# Timeout set to 120s to prevent 502 errors during Cold Boot on Render
timeout = 120

# Worker configuration (Dynamic Port Sync for Render Cloud)
bind = "0.0.0.0:" + os.environ.get("PORT", "10000")
workers = 4 # Standard for Render free/starter tiers
worker_class = "gthread"
threads = 4

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
