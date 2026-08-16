import numpy as np
from pathlib import Path
from mir_utils.metrics import DataRecorder
import matplotlib.pyplot as plt

path = Path(__file__).parent / "rec.npz"
data, metadata = DataRecorder.load(path)    

fig, axs = plt.subplots(len(metadata), 1, figsize=(6, len(metadata)*2))
idx = 0
timestamps = data["__timestamps__"]

for name, entry in metadata.items():
    array = data[name]
    if isinstance(array, np.ndarray):
        ymin = entry.get('min_value')
        ymax = entry.get('max_value')
        min = np.min(array)
        max = np.max(array)
        mean = np.mean(array)
        std = np.std(array)
        info=(f"Min={min:.1f} Max={max:.1f} Mean={mean:.1f} Std={std:.1f}")
        axs[idx].plot(timestamps, array)
        axs[idx].set_title(f"{name} : {info}", fontsize=9) 
        axs[idx].set_ylim(ymin, ymax)
        axs[idx].set_ylabel(entry['unit'],fontsize=9)
        axs[idx].tick_params(axis='both', labelsize=8) 
        axs[idx].grid(True)
        idx += 1
plt.tight_layout()         
plt.show()  
