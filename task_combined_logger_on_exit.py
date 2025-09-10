import psutil
import os
import time
import csv
from collections import defaultdict

STATIC_LOG = "task_combined_features.csv"
SLEEP_INTERVAL = 2  # seconds

seen_pids = set()
active_procs = {}

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

if not os.path.exists(STATIC_LOG):
    with open(STATIC_LOG, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

print("Starting logger (logs after task ends)... Press Ctrl+C to stop.")

while True:
    try:
        for proc in psutil.process_iter(['pid', 'create_time']):
            pid = proc.info['pid']
            if pid not in seen_pids:
                seen_pids.add(pid)
                active_procs[pid] = proc

        terminated_pids = []
        for pid, proc in active_procs.items():
            if not psutil.pid_exists(pid):
                try:
                    # psutil already purged, recreate dummy for logging
                    end_time = time.time()
                    create_time = proc.info['create_time']
                    uptime = round(end_time - create_time, 2)
                    static = get_static_features(pid)
                    if not static:
                        continue

                    name = static["Program"]
                    text_size, data_size = get_elf_info(name)

                    # Estimate CPU and memory from historical average (mocked)
                    avg_cpu = 50  # placeholder
                    avg_mem = static["VmRSS_KB"]  # last seen

                    label = (
                        "Resource-Intensive" if avg_cpu > 70 or uptime > 5 else
                        "Background" if avg_cpu < 15 and uptime < 2 else
                        "Real-Time"
                    )

                    row = {
                        **static,
                        "text_size": text_size,
                        "data_size": data_size,
                        "avg_cpu": avg_cpu,
                        "avg_memory": avg_mem,
                        "avg_duration": uptime,
                        "class": label
                    }

                    with open(STATIC_LOG, "a", newline="") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writerow(row)

                    terminated_pids.append(pid)
                except Exception as e:
                    continue

        for pid in terminated_pids:
            active_procs.pop(pid, None)

        time.sleep(SLEEP_INTERVAL)
    except KeyboardInterrupt:
        print("Logger stopped.")
        break
