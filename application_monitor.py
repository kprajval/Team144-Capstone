import psutil
import time
import csv

def monitor_context_switch(pid):
    try:
        process = psutil.Process(pid)
    except psutil.NoSuchProcess:
        print(f"Process {pid} not found.")
        return

    prev_cpu_time = sum(process.cpu_times()[:2])
    in_cpu = False
    burst_start_time = None
    burst_start_cpu = None
    burst_log = []

    print("Monitoring CPU context switches for PID:", pid)
    print("{:<10} {:<20} {:<15} {:<15} {:<15}".format("Type", "Timestamp", "CPU Used (s)", "CPU (%)", "Memory (MB)"))

    try:
        while True:
            time.sleep(0.1)

            if not process.is_running():
                print("Process exited.")
                break

            current_cpu_time = sum(process.cpu_times()[:2])
            current_time = time.time()

            if current_cpu_time > prev_cpu_time:
                if not in_cpu:
                    # Switch IN
                    burst_start_time = current_time
                    burst_start_cpu = current_cpu_time
                    in_cpu = True
                    print("{:<10} {:<20}".format("IN", burst_start_time))
            else:
                if in_cpu:
                    # Switch OUT
                    burst_end_time = current_time
                    burst_end_cpu = current_cpu_time
                    cpu_used = burst_end_cpu - burst_start_cpu
                    cpu_percent = process.cpu_percent(interval=None)
                    mem_used_mb = process.memory_info().rss / (1024 * 1024)

                    burst_log.append({
                        "Type": "CPU Burst",
                        "Start Time": burst_start_time,
                        "End Time": burst_end_time,
                        "CPU Time (s)": cpu_used,
                        "CPU %": cpu_percent,
                        "Memory (MB)": mem_used_mb
                    })

                    print("{:<10} {:<20} {:<15} {:<15} {:<15}".format(
                        "OUT", burst_end_time, cpu_used, cpu_percent, mem_used_mb))

                    in_cpu = False

            prev_cpu_time = current_cpu_time

    except KeyboardInterrupt:
        print("\nMonitoring stopped. Saving to CSV...")

    # Save to CSV without rounding
    with open("context_switch_log.csv", "w", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["Type", "Start Time", "End Time", "CPU Time (s)", "CPU %", "Memory (MB)"])
        writer.writeheader()
        writer.writerows(burst_log)

    print("Saved context switch log to context_switch_log.csv")

# Run
if __name__ == "__main__":
    pid = int(input("Enter PID to monitor: "))
    monitor_context_switch(pid)
