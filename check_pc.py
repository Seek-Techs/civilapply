# check_pc.py — Run this to see if your PC can run offline AI
# python check_pc.py

import os
import sys
import platform
import subprocess

print("=" * 55)
print("  PC SPECS FOR OFFLINE AI")
print("=" * 55)

print(f"\n  OS        : {platform.system()} {platform.release()}")
print(f"  Python    : {sys.version.split()[0]}")
print(f"  CPU cores : {os.cpu_count()}")

# RAM check
try:
    import ctypes
    kernel32 = ctypes.windll.kernel32
    c_ulong = ctypes.c_ulong
    class MEMORYSTATUS(ctypes.Structure):
        _fields_ = [
            ('dwLength', c_ulong),
            ('dwMemoryLoad', c_ulong),
            ('dwTotalPhys', c_ulong),
            ('dwAvailPhys', c_ulong),
            ('dwTotalPageFile', c_ulong),
            ('dwAvailPageFile', c_ulong),
            ('dwTotalVirtual', c_ulong),
            ('dwAvailVirtual', c_ulong),
        ]
    mem = MEMORYSTATUS()
    mem.dwLength = ctypes.sizeof(MEMORYSTATUS)
    kernel32.GlobalMemoryStatus(ctypes.byref(mem))
    total_gb = mem.dwTotalPhys / (1024**3)
    avail_gb = mem.dwAvailPhys / (1024**3)
    print(f"  RAM total : {total_gb:.1f} GB")
    print(f"  RAM free  : {avail_gb:.1f} GB")
except Exception:
    print("  RAM       : Could not detect (check System settings)")

# Disk space
try:
    total, used, free = os.statvfs('.').f_blocks, 0, 0
except Exception:
    pass
try:
    import shutil
    total, used, free = shutil.disk_usage("C:\\")
    print(f"  Disk free : {free / (1024**3):.1f} GB on C:")
except Exception:
    print("  Disk      : Could not detect")

# Check if Ollama is already installed
print(f"\n{'─'*55}")
print("  OLLAMA STATUS")
print(f"{'─'*55}")
try:
    result = subprocess.run(
        ["ollama", "list"],
        capture_output=True, text=True, timeout=5
    )
    if result.returncode == 0:
        print("  ✓ Ollama is installed")
        lines = result.stdout.strip().splitlines()
        if len(lines) > 1:
            print("  Downloaded models:")
            for line in lines[1:]:
                print(f"    - {line.split()[0] if line.split() else line}")
        else:
            print("  No models downloaded yet")
            print("  Run: ollama pull llama3.2:3b")
    else:
        print("  ✗ Ollama not installed or not running")
        print("  Download from: ollama.com")
except FileNotFoundError:
    print("  ✗ Ollama not installed")
    print("  Download from: ollama.com")
except Exception as e:
    print(f"  Ollama status unknown: {e}")

# Recommendation
print(f"\n{'─'*55}")
print("  RECOMMENDATION")
print(f"{'─'*55}")
try:
    if total_gb >= 16:
        print("  ✅ Excellent — can run llama3.1:8b (best quality)")
        print("     Command: ollama pull llama3.1:8b")
    elif total_gb >= 8:
        print("  ✅ Good — can run llama3.2:3b (good quality, fast)")
        print("     Command: ollama pull llama3.2:3b")
    else:
        print("  ⚠️  RAM may be tight for offline AI")
        print("     Use Cohere API instead (free, cloud-based)")
except Exception:
    print("  Run the RAM check above to get a recommendation")

print("=" * 55)