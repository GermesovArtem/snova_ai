import os
import time
import subprocess
import re
import httpx
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = "6930578591"  # Provided by User
CHECK_INTERVAL_SECONDS = 60
FAIL_THRESHOLD = 5  # Brute force alert threshold
AUTH_LOG_PATH = "/var/log/auth.log"  # Mounted from host

# --- SECURITY SIGNATURES ---
SQL_THREATS = [
    r"CREATE OR REPLACE FUNCTION system",
    r"DROP DATABASE",
    r"pg_sleep",
    r"pg_read_file",
    r"pg_ls_dir",
    r"base64 -d\|bash",
]

API_THREATS = [
    r"\.env",
    r"wp-admin",
    r"phpmyadmin",
    r"cgi-bin",
    r"node_modules",
    r"\.git",
]

# --- STATE ---
IP_FAILURES = {} # IP -> count
LAST_CHECKED_LOG_TIME = datetime.now() - timedelta(minutes=5)
AUTH_LOG_SEEK = 0

def send_telegram_alert(message: str):
    print(f"[SECURITY] Sending Telegram Alert: {message}")
    if not BOT_TOKEN:
        print("[ERROR] BOT_TOKEN not found in environment!")
        return
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ADMIN_ID,
        "text": f"🛡️ **S•NOVA GUARDIAN ALERT** 🛡️\n\n{message}",
        "parse_mode": "Markdown"
    }
    try:
        httpx.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram alert: {e}")

def check_docker_logs(service_name: str, signatures: list, label: str):
    try:
        # Get logs since last minute
        cmd = f"docker logs --since 1m {service_name}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        logs = result.stderr if result.stderr else result.stdout # Docker logs often go to stderr
        
        for sig in signatures:
            matches = re.findall(sig, logs, re.IGNORECASE)
            if matches:
                msg = f"Detected **{label}** threat in `{service_name}` logs!\nPattern: `{sig}`\nCount: {len(matches)}"
                send_telegram_alert(msg)
    except Exception as e:
        print(f"[ERROR] Failed to check docker logs for {service_name}: {e}")

def check_ssh_logs():
    global AUTH_LOG_SEEK
    if not os.path.exists(AUTH_LOG_PATH):
        return
    
    try:
        with open(AUTH_LOG_PATH, "r") as f:
            f.seek(0, 2)
            file_size = f.tell()
            
            # If first run or log rotated
            if AUTH_LOG_SEEK == 0 or file_size < AUTH_LOG_SEEK:
                AUTH_LOG_SEEK = file_size
                return
                
            f.seek(AUTH_LOG_SEEK)
            lines = f.readlines()
            AUTH_LOG_SEEK = f.tell()
            
        for line in lines:
            # Check for failed password
            if "Failed password" in line:
                # Extract IP (basic regex)
                ip_match = re.search(r"from ([\d\.]+)", line)
                if ip_match:
                    ip = ip_match.group(1)
                    IP_FAILURES[ip] = IP_FAILURES.get(ip, 0) + 1
                    if IP_FAILURES[ip] % FAIL_THRESHOLD == 0:
                        send_telegram_alert(f"🔥 **SSH Brute Force Detected!**\nIP: `{ip}`\nFailed attempts: {IP_FAILURES[ip]}\nРекомендуется заблокировать IP.")
            
            # Check for successful login
            if "Accepted password" in line or "Accepted publickey" in line:
                user_match = re.search(r"for (\w+) from", line)
                if user_match:
                    user = user_match.group(1)
                    send_telegram_alert(f"✅ **SSH Login Successful**\nUser: `{user}`\nCheck if this was you!")
    except Exception as e:
        print(f"[ERROR] Failed to check SSH logs: {e}")

def check_system_connections():
    try:
        # Check for non-standard established connections
        # Specifically looking for connections to DB port if it was ever exposed
        # and checking for common reverse shell ports
        result = subprocess.run("ss -tunp", shell=True, capture_output=True, text=True)
        if "established" in result.stdout.lower():
            # Filter for suspicious things if needed
            pass
    except Exception as e:
        print(f"[ERROR] Failed to check system connections: {e}")

def monitor_loop():
    print(f"[INFO] Guardian started. Monitoring Admin ID: {ADMIN_ID}")
    send_telegram_alert("🛡️ *Сервис мониторинга безопасности запущен.* Текущий статус: OK.")
    
    while True:
        try:
            # 1. Check Database logs for SQLi and Hack patterns
            check_docker_logs("snova_ai-db-1", SQL_THREATS, "Postgres Attack")
            
            # 2. Check API logs for vulnerability scanning
            check_docker_logs("snova_ai-api-1", API_THREATS, "Web Vulnerability Scan")
            
            # 3. Check SSH logs for Brute Force
            check_ssh_logs()
            
            # 4. Check for unusual established connections
            check_system_connections()
            
        except Exception as e:
            print(f"[ERROR] Error in monitor loop: {e}")
            
        time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    monitor_loop()
