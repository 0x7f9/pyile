import tkinter as tk
import datetime 
import os

def log(log_area, message):
    log_area.configure(state='normal')
    log_area.insert(tk.END, message + "\n")
    log_area.configure(state='disabled')
    log_area.see(tk.END)
    save_name = 'log.txt'

    # gets relative pathing and goes back three levels to find logging folder
    script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(script_dir, "logging")
    if not os.path.exists(path):
        os.makedirs(path)
    save_path = os.path.join(path, save_name) 
   
    try:
        with open(save_path, "a") as log_file:
            timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
            log_file.write(f"{timestamp} {message}\n")
    except:
        pass

def clear_console(log_area):
    log_area.configure(state='normal')
    log_area.delete('1.0', tk.END)
    log_area.configure(state='disabled')
    
