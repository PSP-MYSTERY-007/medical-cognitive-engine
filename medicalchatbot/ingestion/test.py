import socket
import subprocess
import sys
import time

BACKEND_PORT = 8000
QDRANT_PORT = 6333

def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(('localhost', port)) == 0
    
def run_blocking_command(command, description, cwd=None):
    """Runs a setup command and waits."""
    print(f"⚙️ {description}...")
    try:
        # We pass the cwd variable into the real subprocess.run
        subprocess.run(command, shell=True, check=True, cwd=cwd)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during: {description}")
        sys.exit(1)

def main():
    print("🏥 --- MEDICAL COGNITIVE ENGINE: INGESTION TRIAL --- 🏥\n")

    # 1. Start Qdrant (Docker)
    if not is_port_open(QDRANT_PORT):
        run_blocking_command(
            "docker run -d -p 6333:6333 -p 6334:6334 qdrant/qdrant",
            "Starting Qdrant Vector DB"
        )
        time.sleep(3)
    else:
        print("✅ Qdrant is already online.")

    
    run_blocking_command("python -m medicalchatbot.ingestion.reset", "Cleaning DB")
    run_blocking_command("python -m medicalchatbot.ingestion.ingest", "Ingesting Documents")


if __name__ == "__main__":
    main()