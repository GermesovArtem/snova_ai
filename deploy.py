import paramiko
import os
import sys

IP = '77.221.140.206'
USER = 'root'
PASS = 'lFytYMZ8iNtx'
REPO = 'https://github.com/GermesovArtem/snova_ai.git'
ENV_PATH = r'c:\Users\Пользователь\.gemini\antigravity\scratch\telegram_bot\.env'

def run_cmd(ssh, cmd):
    print(f"\n[REMOTE] {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    
    for line in iter(stdout.readline, ""):
        print("OUT:", line.strip())
        
    err = stderr.read().decode().strip()
    if err:
        print(f"ERR: {err}")
        
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        print(f"WARNING: Command exited with status {exit_status}")
    return exit_status

def main():
    print("Connecting via SSH...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(IP, username=USER, password=PASS, timeout=10)
        
        run_cmd(ssh, "apt-get update -y && DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io docker-compose git")
        
        run_cmd(ssh, "rm -rf snova_ai")
        
        status = run_cmd(ssh, f"git clone {REPO} snova_ai")
        if status != 0:
            print("Failed to clone repository. Proceeding anyway, might be an issue if it doesn't exist.")
            
        print("\n[UPLOAD] Uploading .env file securely...")
        sftp = ssh.open_sftp()
        sftp.put(ENV_PATH, '/root/snova_ai/.env')
        sftp.close()
        
        run_cmd(ssh, "cd snova_ai && docker compose down || true")
        run_cmd(ssh, "cd snova_ai && docker compose build")
        run_cmd(ssh, "cd snova_ai && docker compose up -d")
        
        print("\n✅ Verification:")
        run_cmd(ssh, "cd snova_ai && docker compose ps")
        
    except Exception as e:
        print(f"Deployment failed: {e}")
        sys.exit(1)
    finally:
        ssh.close()

if __name__ == "__main__":
    main()
