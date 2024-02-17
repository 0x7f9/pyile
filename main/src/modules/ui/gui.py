import time
import threading
import pystray
import customtkinter
from tkinter import scrolledtext, filedialog
from pystray import MenuItem as item
from PIL import Image

from modules.config import user_config
from modules.logging import log, clear_console
from modules.file_monitor import monitor
from modules.backup_monitor import backup_monitor

# colours
bg_color = "#333333"  # dark gray background color for console
fg_color = "#ffffff"  # white text color
customtkinter.set_appearance_mode("System") 
customtkinter.set_default_color_theme("dark-blue")  

class interface(customtkinter.CTk):
    def __init__(self):
        # init customtkinter.CTk
        super().__init__()

        # init
        self.monitor_threads = []
        self.monitors = []
        self.icon_thread = []
        self.tray_icon_thread = False
        self.running = False        
        self.save_directory = None
        self.check_current_files = False
        self.checkbox_1_value = False
        self.checkbox_2_value = False
        self.checkbox_3_value = False
        self.checkbox_4_value = False
        self.checkbox_5_value = False
        self.notification_enabled = False

        # create window
        self.title("Pyile")
        self.geometry("940x440")
        self.iconbitmap("main\\src\\modules\\ui\\images\\icon.ico")

        # main grid layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # sidebar frame
        self.sidebar_frame = customtkinter.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(7, weight=1)

        # tabview 
        self.tabview = customtkinter.CTkTabview(self, width=250)
        self.tabview.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        self.tabview.add("console") 
        self.tabview.add("config")   
        self.tabview.tab("console").grid_rowconfigure(0, weight=1)
        self.tabview.tab("console").grid_columnconfigure(0, weight=1)
        self.tabview.tab("config").grid_rowconfigure(5, weight=1)
        self.tabview.tab("config").grid_columnconfigure(3, weight=1)

        # setting up the logging console, loading in config class and paths
        self.console = scrolledtext.ScrolledText(self.tabview.tab("console"), state='disabled', bg=bg_color, fg=fg_color)
        self.console.grid(row=0, column=0, padx=5, pady=0, sticky="nsew")
        # pass through log functuion so we can call it by self.log without having to import log function into each file
        self.get_config = user_config(log=lambda msg: log(self.console, msg))
        self.PATHS = self.get_config.return_paths()

        # main heading
        self.logo_label = customtkinter.CTkLabel(self.sidebar_frame, text="main", font=("Arial", -14), text_color=("grey"))
        self.logo_label.grid(row=0, column=0, padx=5, pady=0, sticky="w")
        
        # buttons in the sidebar
        self.sidebar_button_1 = customtkinter.CTkButton(self.sidebar_frame,command=self.toggle_monitoring, width=130, height=30, font=("Arial", -14), text="Start logging")
        self.sidebar_button_1.grid(row=1, column=0, padx=10, pady=5)

        self.sidebar_button_2 = customtkinter.CTkButton(self.sidebar_frame, command=self.get_directory, width=130, height=30,  font=("Arial", -14), text="Add directory")
        self.sidebar_button_2.grid(row=2, column=0, padx=10, pady=5)

        self.sidebar_button_3 = customtkinter.CTkButton(self.sidebar_frame, command=self.back_up, width=130, height=30, font=("Arial", -14), text="Back up")
        self.sidebar_button_3.grid(row=3, column=0, padx=10, pady=5)

        # misc heading
        self.logo_label = customtkinter.CTkLabel(self.sidebar_frame, text="misc", font=("Arial", -14), text_color=("grey"))
        self.logo_label.grid(row=4, column=0, padx=5, pady=0, sticky="w")

        self.sidebar_button_4 = customtkinter.CTkButton(self.sidebar_frame, command=lambda: clear_console(self.console),width=130, height=30, font=("Arial", -14), text="Clear log")
        self.sidebar_button_4.grid(row=5, column=0, padx=10, pady=5)
  
        self.sidebar_button_5 = customtkinter.CTkButton(self.sidebar_frame, command=self.save_location, width=130, height=30,font=("Arial", -14), text="Backup location")
        self.sidebar_button_5.grid(row=6, column=0, padx=10, pady=5)

        # checkbox and switch frame in second tabview
        self.checkbox_slider_frame = customtkinter.CTkFrame(self.tabview.tab("config"))
        self.checkbox_slider_frame.grid(row=1, column=1, padx=(0, 0), pady=(0, 0), sticky="nsew")

        self.checkbox_1 = customtkinter.CTkCheckBox(self.checkbox_slider_frame, text="Save directories for next logging session", font=("Arial", 14), command=lambda: self.checkbox_checked(1))
        self.checkbox_1.grid(row=1, column=0, pady=(0, 0), padx=10, sticky="nw")

        # not coded
        self.checkbox_2 = customtkinter.CTkCheckBox(self.checkbox_slider_frame, text="Block executables from running", font=("Arial", 14), command=lambda: self.checkbox_checked(2))
        self.checkbox_2.grid(row=2, column=0, pady=(15, 0), padx=10, sticky="nw")

        self.checkbox_3 = customtkinter.CTkCheckBox(self.checkbox_slider_frame, text="Check current files for duplicates before logging", font=("Arial", 14), command=lambda: self.checkbox_checked(3))
        self.checkbox_3.grid(row=3, column=0, pady=(15, 0), padx=10, sticky="nw")

        self.checkbox_4 = customtkinter.CTkCheckBox(self.checkbox_slider_frame, text="Minimise to tray on exit", font=("Arial", 14), command=lambda: self.checkbox_checked(4))
        self.checkbox_4.grid(row=4, column=0, pady=(15, 0), padx=10, sticky="nw")

        self.checkbox_5 = customtkinter.CTkCheckBox(self.checkbox_slider_frame, text="Enable notifications", font=("Arial", 14), command=lambda: self.checkbox_checked(5))
        self.checkbox_5.grid(row=5, column=0, pady=(15, 0), padx=10, sticky="nw")

        # updating/show numbers frame
        self.tally_frame = customtkinter.CTkFrame(self.tabview.tab("config"))
        self.tally_frame.grid(row=1, column=3, padx=25, pady=0,  sticky="ne")
        
        self.heading_label = customtkinter.CTkLabel(self.tally_frame, text="0 Files are the same", font=("Arial", 14))
        self.heading_label.grid(row=0, column=0, padx=0, pady=0, sticky="nw")

        self.heading_label_2 = customtkinter.CTkLabel(self.tally_frame, text="0 Files checked in session", font=("Arial", 14))
        self.heading_label_2.grid(row=1, column=0, padx=0, pady=0, sticky="nw")

        self.heading_label_3 = customtkinter.CTkLabel(self.tally_frame, text=f"Last file checked - no files checked", font=("Arial", 14))
        self.heading_label_3.grid(row=2, column=0, padx=0, pady=0, sticky="nw")
        
        # loading in checkbox states 
        self.get_checkbox_states()


    def save_location(self):
        self.save_directory = self.prompt()


    def start_icon_thread(self):
        self.icon.run()


    def get_checkbox_states(self):
        config = self.get_config.load_checkbox_config()
        if config == None:
            return
        
        checkbox1 = config.get("Checkbox1_value")
        # checkbox2 = config.get("Checkbox2_value")
        checkbox3 = config.get("Checkbox3_value")
        checkbox4 = config.get("Checkbox4_value")
        checkbox5 = config.get("Checkbox5_value")

        if checkbox1 == "True":
            self.checkbox_1_value = True
            self.checkbox_1.select()
            self.get_config.load_directories_config()

        # # not coded
        # if self.checkbox_2_value:
        #     self.checkbox_2.select()

        if checkbox3 == "True":
            self.checkbox_3_value = True
            self.check_current_files = True
            self.checkbox_3.select()

        if checkbox4 == "True":
            self.checkbox_4_value = True
            self.checkbox_4.select()
            self.protocol("WM_DELETE_WINDOW", self.minimize)

        if checkbox5 == "True":
            self.checkbox_5_value = True
            self.notification_enabled = True
            self.checkbox_5.select()


    def updater(self, file_monitor):
        # running in a thread to continuously monitor and update gui values
        while 1:
            last_file, count, match = file_monitor.return_value()
            self.update_values(last_file, count, match)
            time.sleep(1) # CPUUUUUU


    def update_values(self, last_file, count, match):
        # send updated values
        self.heading_label.configure(text=f"{match} Files are the same")
        self.heading_label_2.configure(text=f"{count} Files checked today")
        
        if last_file == None:
            return

        self.heading_label_3.configure(text=f"Last file checked - {last_file}")
        

    def checkbox_checked(self, checkbox):
        # save directories on exit 
        if checkbox == 1:
            self.checkbox_1_value = not self.checkbox_1_value
            if self.checkbox_1_value:
                self.get_config.make_directories_config()
                
                for path in self.PATHS:
                     self.get_config.save_directories_config(path)
        
        # # not coded yet
        # elif checkbox == 2:
        #     self.checkbox_2_value = not self.checkbox_2_value
        #     if self.checkbox_2_value:
        #         pass

        # check for file duplicates
        elif checkbox == 3:
            self.checkbox_3_value = not self.checkbox_3_value
            if self.checkbox_3_value:
                self.check_current_files = True
            else:
                 self.check_current_files = False

        # minimise to tray on exit
        elif checkbox == 4:
            self.checkbox_4_value = not self.checkbox_4_value
            if self.checkbox_4_value:
                self.protocol("WM_DELETE_WINDOW", self.minimize)
            else:
                self.protocol("WM_DELETE_WINDOW", self.destroy)
                self.stop_icon_thread()
        # desktop notfication
        elif checkbox == 5:
            self.checkbox_5_value = not self.checkbox_5_value
            if self.checkbox_5_value:
                self.notification_enabled = True
            else:
                self.notification_enabled = False

        else:
            return 
       
        self.get_config.save_checkbox_config(self.checkbox_1_value, self.checkbox_2_value, self.checkbox_3_value, self.checkbox_4_value, self.checkbox_5_value)
        

    def stop_icon_thread(self):
        try:
            self.tray_icon_thread = False
            self.icon.stop()
            self.icon_thread.join()
            self.icon_thread = None
        except:
            log(self.console, "Error stopping icon thread")


    def exit_application(self):
        # todo - if backup running do a backup before quiting 
        # self.start_backup(directory, self.save_directory)
        self.stop_icon_thread()
        self.destroy()
        self.quit()
        exit()


    def icon_clicked(self, none, item):
        if item.text == 'exit':
            # send the kill signal back to the main thread using after
            self.after(0, self.exit_application)

        elif item.text == 'show':
            self.deiconify()


    def start_icon(self):
        self.tray_icon_thread = True
        tooltip = "Pyile - File Monitor"

        # create system tray icon with default left click action
        image = Image.open("main\\src\\modules\\ui\\images\\tray_icon.png")
        menu = (
            item('exit', self.icon_clicked), 
            item('show', self.icon_clicked, default=True, visible=False)
        )
        self.icon = pystray.Icon("name", image, menu=menu)
        self.icon.title = tooltip
        self.icon_thread = threading.Thread(target=self.start_icon_thread, daemon=True)
        self.icon_thread.start()


    def minimize(self):
        self.iconify()
        self.withdraw()
        if not self.tray_icon_thread:
            self.start_icon()


    def start_backup(self, directory, save_directory):
        # pass through log functuion so we can call it by self.log without having to import log function into each file
        _monitor = backup_monitor(directory, save_directory, log=lambda msg: log(self.console, msg))
        monitor_thread = threading.Thread(target=_monitor.main, daemon=True)
        monitor_thread.start()
        log(self.console, f"Started backups for {directory}")


    def back_up(self):
        try:
            directory = self.prompt()
            if directory:
                self.start_backup(directory, self.save_directory)
            else:
                return
        except:
            pass


    def toggle_monitoring(self):
        if self.monitor_threads:
            self.stop_monitoring()
        else:
            self.start_monitoring()


    def start_monitoring(self):
        if not self.PATHS:
            log(self.console, "There are no directories to monitor")
            return
        
        self.sidebar_button_1.configure(text="Stop logging")
        for path in self.PATHS:
            # pass through log functuion so we can call it by self.log without having to import log function into each file
            file_monitor = monitor(path, check_current_files=self.check_current_files, notification_enabled=self.notification_enabled, log=lambda msg: log(self.console, msg))
            
            # start a thread for each path to keep track of the updated values
            update_thread = threading.Thread(target=self.updater, args=(file_monitor,), daemon=True)
            update_thread.start()
            
            monitor_thread = threading.Thread(target=file_monitor.main, daemon=True)
            self.monitor_threads.append(monitor_thread)  
            self.monitors.append(file_monitor)
            monitor_thread.start()


    def stop_monitoring(self):
        self.sidebar_button_1.configure(text="Start logging")
        log(self.console, "Stopping file logging...")
        for file_monitor in self.monitors: 
            # calling stop function in file_monitor
            file_monitor.stop() 
        for thread in self.monitor_threads:
            thread.join(timeout=1)
        self.monitor_threads.clear()
        self.monitors.clear()
        log(self.console, "File logging stopped\n")


    def prompt(self):
        directory = filedialog.askdirectory()
        if directory:
            log(self.console, f"selected directory {directory}")
            return directory
        else:
            log(self.console,"no directory selected")
            

    def get_directory(self):
        input_file = set()
        if not input_file:
            directory = self.prompt()
            self.PATHS.append(directory)

            if self.checkbox_1_value:
                self.get_config.save_directories_config(directory)

