# filepath: /Users/qijunfang/Documents/Job_Hunting_202504/Global Partners/weather-microservice-demo/app/main.py
import time
import subprocess

print("Weather microservice is running...")

# Run the equivalent of the bash command
subprocess.run(
    ["python", "app/load/load_gridpoints.py", "--batch-size", "1000", "--num_rows", "5000"],
    check=True
)

# while True:
#     time.sleep(10)

# print("Weather microservice has completed the task.")