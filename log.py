import os
from time import localtime

def parse_current_time():
    current_time = localtime()
    return {
        'year': current_time[0],
        'month': current_time[1],
        'day': current_time[2],
        'hour': current_time[3],
        'second': current_time[5]
    }

def log(text):
    current_time = parse_current_time()
    filename = "{:02d}{:02d}{}.err.log".format(
        current_time['day'], current_time['month'], current_time['year']
    )
    log_entry = "\n[{}:{}] {}".format(current_time['hour'], current_time['second'], text)
    
    # Open the file and append the log entry
    with open(filename, 'a') as log_file:
        log_file.write(log_entry)

# Example usage
log("This is a test log entry.")
