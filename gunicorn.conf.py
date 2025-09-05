# gunicorn configuration file
import multiprocessing

# Server socket
bind = '0.0.0.0:10000'  # Use the PORT environment variable if set, otherwise default to 10000

# Worker processes - Optimized for 512MB memory limit
workers = 1  # Only 1 worker for free tier
worker_class = 'gthread'  # Use threads for I/O-bound applications
threads = 2  # 2 threads per worker
worker_connections = 1000
max_requests = 500  # Restart workers more frequently to prevent memory leaks
max_requests_jitter = 50  # Add jitter to prevent all workers from restarting simultaneously

# Timeouts
timeout = 120  # Increased timeout for better stability
keepalive = 2  # Seconds to wait for requests on a Keep-Alive connection

# Logging
accesslog = '-'  # Log to stdout
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)s'
errorlog = '-'  # Log to stderr
loglevel = 'info'
capture_output = True  # Redirect stdout/stderr to specified file in errorlog

# Process naming
proc_name = 'maua-sacco'

# Security
# Prevents the application from being available on shared servers
# Only needed if you're running multiple applications on the same server
# worker_tmp_dir = '/dev/shm'  # For better performance on Linux

# Debugging
reload = False  # Don't use in production, only for development
