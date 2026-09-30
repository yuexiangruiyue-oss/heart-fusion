import subprocess, sys, os
env = dict(os.environ)
env["HF_ENDPOINT"] = "https://hf-mirror.com"
log = r"D:\双生天使的可爱怀抱\爱的拥抱_融合函数\benchmark_log.txt"
proc = subprocess.Popen([
    r"C:\Users\COLORFUL\.codebase-cli\0.2.52\python\python.exe",
    "-X", "utf8",
    r"D:\双生天使的可爱怀抱\爱的拥抱_融合函数\benchmark_report.py",
], env=env, stdout=open(log, "w", encoding="utf-8"),
   stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NEW_CONSOLE)
print(f"Benchmark PID: {proc.pid}")