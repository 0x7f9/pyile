import time
import os
import win32file
import zipfile
# import zstandard as zstd
from datetime import datetime, timedelta

from . import *

class backup_monitor:
    def __init__(self, path, save_directory, log):
        self.path = path
        self.handle = None
        self.log = log
        self.is_running = True
        self.timestamp = None
        self.time_left = None
        self.save_directory = save_directory


    def get_handle(self):
        handle = win32file.CreateFile(
            self.path,
            FILE_LIST_DIRECTORY,
            FILE_SHARE_READ | 
            FILE_SHARE_WRITE |
            FILE_SHARE_DELETE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS,
            None
        )
        return handle
    
    
    def get_changes(self):
        changes = win32file.ReadDirectoryChangesW(
            self.handle,
            1024,
            True,
            FILE_NOTIFY_CHANGE_ATTRIBUTES |
            FILE_NOTIFY_CHANGE_DIR_NAME |
            FILE_NOTIFY_CHANGE_FILE_NAME |
            FILE_NOTIFY_CHANGE_LAST_WRITE |
            FILE_NOTIFY_CHANGE_SECURITY |
            FILE_NOTIFY_CHANGE_SIZE,
            None,
            None
        )
        return changes
    

    def get_current_timestamp(self):
        return datetime.now()


    def update_timestamp(self):
        self.timestamp = self.get_current_timestamp()

    
    def compress_backup(self, name):
        # todo add a compressor with a way to decompress
        # compressor = zstd.ZstdCompressor()
        save_directory = None  
        if self.save_directory:
            backup_directory = os.path.join(self.save_directory, "backup")
            if not os.path.exists(backup_directory):
                os.makedirs(backup_directory)
            save_directory = os.path.join(backup_directory, name)

        else:
            # gets relative pathing and goes back three levels to find backup folder
            script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            path = os.path.join(script_dir, "backup")
            if not os.path.exists(path):
                os.makedirs(path)
            save_directory = os.path.join(path, name) 

        with zipfile.ZipFile(save_directory, 'w') as zipf:
            for root, dirs, files in os.walk(self.path):
                for file in files:
                    file_path = os.path.join(root, file)
                    with open(file_path, 'rb') as f:
                        # compressed_data = compressor.compress(f.read())
                        data = f.read()
                    zipf.writestr(os.path.relpath(file_path, self.path), data)

                if dirs:
                    for directory in dirs:
                        dir_path = os.path.join(root, directory)
                    zipf.write(dir_path, os.path.relpath(dir_path, self.path))


    def check_backup_timer(self):
        # backup timer allowing backups every 15 mins
        now = datetime.now()
        time_difference = now - self.timestamp
        fifteen_minutes = timedelta(minutes=15)
        self.time_left =  fifteen_minutes - time_difference

        return time_difference >= fifteen_minutes
    

    def check_time(self):
        # check timestamps if it has been 15 mins from the last timestamp then copy all files to somewhere 
        
        if self.check_backup_timer():
            self.compress_backup('backup.zip')
            self.update_timestamp()
        else:
            self.log(f"Waiting for backup timer. Time left: {self.time_left}")


    def monitor_handle(self, path_filename):
        # detecting what changes occurred after being notified

        if self.handle == FILE_ACTION_ADDED:
            self.log("backup needed")
            self.check_time()

        elif self.handle == FILE_ACTION_REMOVED:
            self.log("backup needed")
            self.check_time()
            
        elif self.handle == FILE_ACTION_MODIFIED:
            self.log("backup needed")
            self.check_time()

        else:
            self.log(f"Unknown action on: {path_filename}")


    def main(self):
        # main backup

        if self.timestamp is None:
            self.log("first back up done")
            self.compress_backup('backup.zip')
            self.update_timestamp()

        while 1:
            try:
                self.handle = self.get_handle()

                for self.handle, filename in self.get_changes():
                    path_filename = os.path.join(self.path, filename)
                    self.monitor_handle(path_filename)

                time.sleep(1) # -_- 

            except Exception as e:
                self.log(f"!! BIG Error during backup runtime !!: {e}")

