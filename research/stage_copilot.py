import os, subprocess, shutil

print("=== Colab A100 VM Verification ===")
gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], capture_output=True, text=True)
print(f"GPU: {gpu.stdout.strip()}")

# Direct datacenter download of copilot binary
url = "https://github.com/github/copilot-cli/releases/download/v1.0.102/copilot-win32-x64.zip"
print(f"Downloading GitHub Copilot CLI v1.0.102 from {url}...")
subprocess.run(["wget", "-q", url, "-O", "/content/copilot.zip"], check=True)
subprocess.run(["unzip", "-q", "-o", "/content/copilot.zip", "-d", "/content/copilot_pkg"], check=True)

# Find copilot.exe
copilot_exe = None
for root, dirs, files in os.walk("/content/copilot_pkg"):
    for f in files:
        if f.lower() == "copilot.exe":
            copilot_exe = os.path.join(root, f)
            break

if copilot_exe:
    shutil.copy(copilot_exe, "/content/copilot.EXE")
    size_mb = os.path.getsize("/content/copilot.EXE") / (1024 * 1024)
    print(f"Successfully staged /content/copilot.EXE ({size_mb:.2f} MB)")
else:
    print("Listing extracted contents:")
    for root, dirs, files in os.walk("/content/copilot_pkg"):
        for f in files:
            print(" ", os.path.join(root, f))
