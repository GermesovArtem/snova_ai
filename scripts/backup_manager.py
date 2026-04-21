import os
import time
import subprocess
import boto3
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# S3 Config
S3_ENDPOINT = os.getenv("S3_ENDPOINT_URL")
S3_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET = os.getenv("S3_SECRET_KEY")
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
S3_PREFIX = "backups/"

# DB Config
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_HOST = "db"
DB_NAME = os.getenv("POSTGRES_DB", "nanobanana")

# Backup Interval (3 hours)
BACKUP_INTERVAL_SECONDS = 3 * 3600

def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_KEY,
        aws_secret_access_key=S3_SECRET
    )

def run_backup():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"backup_{timestamp}.sql.gz"
    local_path = f"/tmp/{filename}"
    
    print(f"[{datetime.now()}] Initializing backup: {filename}")
    
    # Run pg_dump and compress
    # We use PGPASSWORD env var to avoid interactivity
    env = os.environ.copy()
    env["PGPASSWORD"] = os.getenv("POSTGRES_PASSWORD")
    
    cmd = f"pg_dump -h {DB_HOST} -U {DB_USER} {DB_NAME} | gzip > {local_path}"
    
    try:
        subprocess.run(cmd, shell=True, check=True, env=env)
        
        # Upload to S3
        s3 = get_s3_client()
        s3_key = f"{S3_PREFIX}{filename}"
        s3.upload_file(local_path, S3_BUCKET, s3_key)
        
        print(f"[{datetime.now()}] Backup successfully uploaded to S3: {s3_key}")
        
    except Exception as e:
        print(f"[ERROR] Backup failed: {e}")
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)

def prune_old_backups():
    print(f"[{datetime.now()}] Checking for old backups (7 day retention)...")
    s3 = get_s3_client()
    try:
        response = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=S3_PREFIX)
        if 'Contents' in response:
            cutoff = datetime.now(datetime.now().astimezone().tzinfo) - timedelta(days=7)
            for obj in response['Contents']:
                if obj['LastModified'] < cutoff:
                    print(f"Deleting expired backup: {obj['Key']}")
                    s3.delete_object(Bucket=S3_BUCKET, Key=obj['Key'])
    except Exception as e:
        print(f"[ERROR] Pruning failed: {e}")

def main():
    print("--- S NOVA BACKUP MANAGER STARTED ---")
    while True:
        try:
            run_backup()
            prune_old_backups()
        except Exception as e:
            print(f"[CRITICAL] Error in backup loop: {e}")
            
        print(f"Next backup in 3 hours...")
        time.sleep(BACKUP_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
