import subprocess
import time
import socket
import sys
import os

# --- SETTINGS ---
BACKEND_PORT = 8000
QDRANT_PORT = 6333
OLLAMA_PORT = 11434
FRONTEND_DIR = "frontend"
FRONTEND_FILE = "frontend_app.py"
VENV_DIR = ".venv"

def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(('localhost', port)) == 0

def get_venv_python():
    """Returns the path to the python executable inside the venv."""
    if sys.platform == "win32":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")

def setup_virtual_environment():
    """Ensures venv exists and requirements are installed."""
    if not os.path.exists(VENV_DIR):
        print(f"🛠️  Creating virtual environment in {VENV_DIR}...")
        subprocess.run([sys.executable, "-m", "venv", VENV_DIR], check=True)
    
    python_exe = get_venv_python()
        
    if os.path.exists("requirements.txt"):
        print("📦 Installing/Updating requirements...")
        subprocess.run([python_exe, "-m", "pip", "uninstall", "-y", "onnxruntime", "onnxruntime-gpu"], check=True)
    
    # 2. Install the GPU version specifically using the CUDA 12 index
        subprocess.run([python_exe, "-m", "pip", "install", "--upgrade", "pip"], check=True)
        subprocess.run([python_exe, "-m", "pip", "install", "-c", "constraints.txt", "-r", "requirements.txt"], check=True)
        subprocess.run([python_exe, "-m", "pip", "uninstall", "-y", "onnxruntime", "onnxruntime-gpu"], check=True)
#        subprocess.run([
#            python_exe, "-m", "pip", "install", "onnxruntime-gpu", 
#            "--extra-index-url", "https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/onnxruntime-cuda-12/pypi/simple/"
#        ], check=True)
        subprocess.run([python_exe, "-m", "pip", "install", "onnxruntime-gpu[cuda,cudnn]"], check=True)
        import onnxruntime as ort
        print(ort.get_available_providers())
    else:
        print("⚠️  No requirements.txt found. Skipping dependency install.")
        import onnxruntime as ort
        print(ort.get_available_providers())

def start_background_process(command, description, cwd=None):
    """Starts a process in the background using the venv python."""
    print(f"🚀 {description}...")
    # Prepend the venv python path if we are running a python command
    if command.startswith("python "):
        command = command.replace("python", get_venv_python(), 1)
    return subprocess.Popen(command, shell=True, cwd=cwd)

def run_blocking_command(command, description, cwd=None):
    """Runs a setup command and waits, using the venv python."""
    print(f"⚙️  {description}...")
    if command.startswith("python "):
        command = command.replace("python", get_venv_python(), 1)
    
    try:
        subprocess.run(command, shell=True, check=True, cwd=cwd)
    except subprocess.CalledProcessError:
        print(f"❌ Error during: {description}")
        sys.exit(1)

def main():
    print("🏥 --- MEDICAL COGNITIVE ENGINE: ALL-IN-ONE BOOT --- 🏥\n")

    # 0. Setup Environment
    setup_virtual_environment()

    # 1. Start Qdrant (Docker)
    if not is_port_open(QDRANT_PORT):
        run_blocking_command(
            "docker run -d -p 6333:6333 -p 6334:6334 qdrant/qdrant",
            "Starting Qdrant Vector DB"
        )
        time.sleep(3)
    else:
        print("✅ Qdrant is already online.")

    # 2. Start Ollama
    if not is_port_open(OLLAMA_PORT):
        # Note: 'ollama serve' is a system binary, not a python script
        start_background_process("ollama serve", "Starting Ollama Service")
        time.sleep(5)
    else:
        print("✅ Ollama is already online.")

    # 3. Optional Maintenance
    confirm = input("🧪 Run Database Refresh (Reset + Ingest)? (y/n): ").lower()
    if confirm == 'y':
        run_blocking_command("python -m medicalchatbot.ingestion.reset", "Cleaning DB")
        run_blocking_command("python -m medicalchatbot.ingestion.ingest", "Ingesting Documents")

    # 4. Start the Backend API
    if not is_port_open(BACKEND_PORT):
        start_background_process("python main.py", "Launching FastAPI Backend")
        print("⏳ Waiting for Backend to initialize...")
        attempts = 0
        while not is_port_open(BACKEND_PORT) and attempts < 15:
            time.sleep(2)
            attempts += 1
    else:
        print("⚠️  Backend port 8000 is already busy!")
    
    # 5. Start Frontend
    print("🎨 Launching Streamlit UI...")
    
    # Use the absolute path or root-relative path for the venv python
    python_exe = get_venv_python()
    
    # Path to the file relative to the ROOT directory (e.g., "frontend/frontend_app.py")
    frontend_path = os.path.join(FRONTEND_DIR, FRONTEND_FILE)
    
    # We run from ROOT, so we don't pass cwd=FRONTEND_DIR
    frontend_cmd = f"{python_exe} -m streamlit run {frontend_path}"
    
    # This ensures the script sees the .venv and the frontend file simultaneously
    run_blocking_command(frontend_cmd, "Opening Browser")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        sys.exit(0)