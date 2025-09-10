
import psutil
import os
import time
import csv
from collections import defaultdict

STATIC_LOG = "task_combined_features.csv"
SLEEP_INTERVAL = 5  # seconds

# Initialize seen processes
seen_pids = set()

# Combined fieldnames
fieldnames = [
    "PID", "Program", "User", "Nice", "Priority", "Threads",
    "VmSize_KB", "VmRSS_KB", "SchedulingPolicy",
    "text_size", "data_size",
    "avg_cpu", "avg_memory", "avg_duration",
    "class"
]

def get_program_name(pid):
    try:
        return open(f"/proc/{pid}/comm").read().strip()
    except:
        return "unknown"

def get_elf_info(program):
    try:
        output = os.popen(f"size $(which {program})").readlines()
        if len(output) < 2:
            return 0, 0
        parts = output[1].split()
        text, data = int(parts[0]), int(parts[1])
        return text, data
    except:
        return 0, 0

def get_static_features(pid):
    try:
        proc = psutil.Process(pid)
        with open(f"/proc/{pid}/status") as f:
            status = f.read()

        threads = int([line for line in status.splitlines() if "Threads:" in line][0].split(":")[1].strip())
        vmrss_line = [line for line in status.splitlines() if "VmRSS:" in line]
        vmsize_line = [line for line in status.splitlines() if "VmSize:" in line]
        vmrss = int(vmrss_line[0].split()[1]) if vmrss_line else 0
        vmsize = int(vmsize_line[0].split()[1]) if vmsize_line else 0

        try:
            sched_policy = os.popen(f"chrt -p {pid}").read().splitlines()[0].split(":")[-1].strip()
        except:
            sched_policy = "unknown"

        return {
            "PID": pid,
            "Program": proc.name(),
            "User": proc.username(),
            "Nice": proc.nice(),
            "Priority": proc.nice(),
            "Threads": threads,
            "VmSize_KB": vmsize,
            "VmRSS_KB": vmrss,
            "SchedulingPolicy": sched_policy
        }

    except (psutil.NoSuchProcess, psutil.AccessDenied, FileNotFoundError):
        return None

# Write header
if not os.path.exists(STATIC_LOG):
    with open(STATIC_LOG, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

print("Starting combined logger. Press Ctrl+C to stop...")

while True:
    process_profiles = defaultdict(lambda: {"cpu": [], "mem": [], "dur": [], "text": 0, "data": 0})

    for proc in psutil.process_iter(['pid', 'cpu_percent', 'memory_info', 'create_time']):
        pid = proc.info['pid']

        if pid not in seen_pids:
            static = get_static_features(pid)
            if static:
                name = static["Program"]
                try:
                    cpu = proc.cpu_percent(interval=0.1)
                    mem = proc.memory_info().rss // 1024
                    uptime = time.time() - proc.info['create_time']
                except:
                    continue

                text_size, data_size = get_elf_info(name)

                row = {
                    **static,
                    "text_size": text_size,
                    "data_size": data_size,
                    "avg_cpu": round(cpu, 2),
                    "avg_memory": round(mem, 2),
                    "avg_duration": round(uptime, 2),
                    "class": (
                        "Resource-Intensive" if cpu > 70 or uptime > 5 else
                        "Background" if cpu < 15 and uptime < 2 else
                        "Real-Time"
                    )
                }

                with open(STATIC_LOG, "a", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writerow(row)

                seen_pids.add(pid)

    time.sleep(SLEEP_INTERVAL)
