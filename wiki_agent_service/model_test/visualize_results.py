import json
import matplotlib.pyplot as plt
import numpy as np
import os

# DATA LOADING
logs_dir = os.path.dirname(os.path.abspath(__file__))
# Auto-detect JSON files
files = [f for f in os.listdir(logs_dir) if f.endswith('.json')]

data = {}
for f in files:
    path = os.path.join(logs_dir, f)
    with open(path, 'r') as file:
        j = json.load(file)
        # Simplify model name for the label
        name = j['model'].split('/')[-1].replace('llama-3.2-', 'Llama ').replace('ibm_granite-4-h-', 'Granite ')
        name = name.replace('-instruct', '').replace('-tiny', '').replace('_', ' ').title()
        data[name] = j

# METRICS CALCULATION
models = list(data.keys())
avg_times = [data[m]['summary']['avg_time'] for m in models]
avg_srcs = [data[m]['summary']['avg_sources'] for m in models]

# Calculate Unique Sources (Diversity)
unique_counts = []
for m in models:
    all_titles = []
    for it in data[m]['iterations']:
        all_titles.extend([t.lower().strip() for t in it['dossier_titles']])
    unique_counts.append(len(set(all_titles)))

# Calculate Efficiency (Sources per Second)
efficiency = [src / t for src, t in zip(avg_srcs, avg_times)]

# Determine Title Config
first_model = list(data.keys())[0]
first_json = data[first_model]
context = first_json.get('context_window', 'Unknown')
cycles = first_json.get('config', {}).get('forced_cycles', '?')
searches = first_json.get('config', {}).get('max_searches', '?')

# PLOTTING
fig, axs = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle(f'Deep Research Benchmark: Llama 3.2 3B vs Granite 4.0 H Tiny\nContext: {context} Tokens | {cycles} Cycles | {searches} Max Searches', fontsize=16)

# 1. Total Time (Lower is Better)
colors = ['#ff9999', '#66b3ff']
axs[0, 0].bar(models, avg_times, color=colors, alpha=0.8, edgecolor='black')
axs[0, 0].set_title('Avg Research Session Duration (Seconds)', fontsize=12)
axs[0, 0].set_ylabel('Seconds')
for i, v in enumerate(avg_times):
    axs[0, 0].text(i, v + 1, f"{v:.1f}s", ha='center', fontweight='bold')

# 2. Sources Found (Higher is Better)
axs[0, 1].bar(models, avg_srcs, color=colors, alpha=0.8, edgecolor='black')
axs[0, 1].set_title('Avg Valid Sources Found per Session', fontsize=12)
for i, v in enumerate(avg_srcs):
    axs[0, 1].text(i, v + 0.5, f"{v:.1f}", ha='center', fontweight='bold')

# 3. Vocabulary Diversity (Unique Titles across 5 runs)
axs[1, 0].bar(models, unique_counts, color=['#ffcc99', '#99ff99'], alpha=0.8, edgecolor='black')
axs[1, 0].set_title('Vocabulary Diversity (Unique Articles Found)', fontsize=12)
axs[1, 0].set_ylabel('Unique Titles Count')
for i, v in enumerate(unique_counts):
    axs[1, 0].text(i, v + 1, str(v), ha='center', fontweight='bold')
axs[1, 0].text(0.5, 0.9, "Measures ability to find\nobscure/non-repetitive info", 
               transform=axs[1, 0].transAxes, ha='center', fontsize=9, style='italic', 
               bbox=dict(facecolor='white', alpha=0.5))

# 4. Sources per Second (Efficiency)
axs[1, 1].bar(models, efficiency, color=['#c2f0f0', '#ffb3e6'], alpha=0.8, edgecolor='black')
axs[1, 1].set_title('Research Efficiency (Sources / Second)', fontsize=12)
for i, v in enumerate(efficiency):
    axs[1, 1].text(i, v + 0.02, f"{v:.2f}", ha='center', fontweight='bold')

plt.tight_layout(rect=[0, 0.03, 1, 0.95])

# Add Summarizing Data Table
cell_text = []
for m in models:
    row = [
        m,
        f"{data[m]['summary']['avg_time']:.2f}s",
        f"{data[m]['summary']['avg_sources']:.1f}",
        f"{[len(set([t.lower() for it in data[m]['iterations'] for t in it['dossier_titles']]))][0]}",
        f"{data[m]['summary']['avg_sources'] / data[m]['summary']['avg_time']:.2f}"
    ]
    cell_text.append(row)

columns = ('Model', 'Avg Time', 'Avg Sources', 'Unique Depth', 'Efficiency')
table = plt.table(cellText=cell_text, colLabels=columns, loc='bottom', bbox=[0.0, -0.3, 1.0, 0.2])
table.auto_set_font_size(False)
table.set_fontsize(10)

save_path = os.path.join(logs_dir, 'benchmark_report.pdf')
plt.savefig(save_path, bbox_inches='tight')
print(f"PDF Report saved to: {save_path}")
