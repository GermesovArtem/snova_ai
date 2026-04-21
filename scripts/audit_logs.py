import os
import subprocess
import re
from datetime import datetime

# --- CONFIGURATION ---
SIGNATURES = [
    r"CREATE OR REPLACE FUNCTION system",
    r"DROP DATABASE",
    r"pg_sleep",
    r"pg_read_file",
    r"pg_ls_dir",
    r"base64 -d\|bash",
    r"wallet",
    r"miner",
    r"\.env",
    r"wp-login",
    r"phpmyadmin",
    r"config\.php",
    r"readme_to_recover",
    r"Failed password",
]

def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout
    except Exception as e:
        return f"Error: {e}"

def audit():
    print(f"--- S NOVA SECURITY AUDIT STARTED AT {datetime.now()} ---")
    
    # 1. Check Docker logs (historical)
    print("\n[+] Checking historical Docker logs (last 5000 lines)...")
    services = ["snova_ai-db-1", "snova_ai-api-1"]
    for svc in services:
        print(f"  - Auditing {svc}...")
        logs = run_cmd(f"docker logs --tail 5000 {svc}")
        for sig in SIGNATURES:
            if re.search(sig, logs, re.IGNORECASE):
                print(f"    !!! WARNING: Found '{sig}' in {svc} logs!")
                
    # 2. Check for suspicious files in /tmp
    print("\n[+] Checking /tmp directory for suspicious files...")
    tmp_list = run_cmd("ls -la /tmp")
    print(tmp_list)
    
    # 3. Check current open ports (listening)
    print("\n[+] Checking listening ports...")
    ports = run_cmd("ss -tuln")
    print(ports)
    
    # 4. Check for unusual processes
    print("\n[+] Checking for unusual processes (miner, bash, etc)...")
    procs = run_cmd("ps aux | grep -E 'miner|wallet|nc|ncat|bash -i'")
    print(procs)

    print(f"\n--- AUDIT COMPLETE AT {datetime.now()} ---")
    print("If you see 'DROP DATABASE' or 'system' function creation, your server was previously compromised.")

if __name__ == "__main__":
    audit()
