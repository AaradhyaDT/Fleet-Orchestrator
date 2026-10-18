import json, os, platform, psutil, time, torch
from pathlib import Path

RAMDISK = Path('/dev/shm/azmuth_burst')
RAMDISK.mkdir(parents=True, exist_ok=True)
OUT = Path('/content/hyperburst_results.json')

dev = torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'
vram = torch.cuda.get_device_properties(0).total_memory / (1024**3) if torch.cuda.is_available() else 0
ram = psutil.virtual_memory().total / (1024**3)

print('ACCEL:', dev, 'VRAM:', vram, 'GB', 'RAM:', ram, 'GB')
shocks = torch.randn(10000, 27, device='cuda')
w = torch.rand(27, 27, device='cuda')
res = torch.matmul(shocks, w)
var99 = torch.quantile((res > 2.0).sum(dim=1).float(), 0.99).item()

payload = {'accelerator': dev, 'vram_gb': round(vram, 2), 'system_ram_gb': round(ram, 2), 'var99': round(var99, 2)}
with open(OUT, 'w') as f: json.dump(payload, f)
print('SUCCESS_WRITTEN')