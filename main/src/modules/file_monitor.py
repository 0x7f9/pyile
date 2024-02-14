import time
import os
import win32file
import win32security
import threading
import hashlib
import concurrent.futures
import multiprocessing
import win32api
from queue import Queue

from . import *
from modules.ui.notifier import trigger_notfication

class monitor:
    def __init__(self, path=None, check_current_files=None, notification_enabled=None, log=None,):
        self.check_current_files = check_current_files
        self.notification_enabled = notification_enabled
        self.path = path
        self.handle = None
        self.contents = None
        self.old_name = None
        self.log = log
        self.is_running = True
        self.last_file = None
        self.file_count = 0
        self.match_count = 0
        self.file_hashes = {}
        self.processed_files = set()

        # hashing thread pool for checking current files
        self.cores_to_use  = multiprocessing.cpu_count() - 2
        self.threads = concurrent.futures.ThreadPoolExecutor(max_workers=self.cores_to_use)

        # notfication thread queue
        self.notification_queue = Queue()
        self.notification_thread = threading.Thread(target=self.process_notifications, daemon=True)
        self.notification_thread.start()
    

    def stop(self):
        self.is_running = False
    
    
    def queue_notification(self, path_filename, event):
        notfi_tuple = (path_filename, event)
        self.notification_queue.put(notfi_tuple)
    
    
    def return_value(self):
        last = self.last_file 
        count = self.file_count
        match = self.match_count
        return last, count, match


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


    def get_username(self, path_filename):
        try:
            # returns the username associated with the file change or file owner
            file_security = win32security.GetFileSecurity(path_filename, win32security.OWNER_SECURITY_INFORMATION)
            sid = file_security.GetSecurityDescriptorOwner()
            account, _, _ = win32security.LookupAccountSid(None, sid)
            return account
        except:
            # returns the user account signed in to the system
            return win32api.GetUserName()


    def process_notifications(self):
        while 1:
            # checks if there is a file in the queue if not it will pause the thread
            path_filename, event = self.notification_queue.get()
            info = path_filename.split("\\")[3:]
            info = "\\".join(info)
            if event == FILE_ACTION_ADDED: 
                trigger_notfication("Click to open file", f"File added\n{info}", 2, on_click=lambda: self.notfication(path_filename))
            elif event == FILE_ACTION_REMOVED:
                trigger_notfication("Click to close notification", f"File removed\n{info}", 2, on_click=lambda: self.notfication(path_filename))
            elif event == FILE_ACTION_MODIFIED:
                trigger_notfication("Click to open file", f"File modified\n{info}", 2, on_click=lambda: self.notfication(path_filename))

            # time.sleep(2) 
            self.notification_queue.task_done()


    def monitor_handle(self, filename, path_filename, username):
        # detecting what changes occurred after being notified
        
        if self.handle == FILE_ACTION_ADDED:
            if self.notification_enabled:
                event = self.handle   
                self.queue_notification(path_filename, event)

            self.log(f"+ User: {username} Created: {path_filename}")
            self.check_file(path_filename, filename)

        elif self.handle == FILE_ACTION_REMOVED:
            if self.notification_enabled:
                event = self.handle   
                self.queue_notification(path_filename, event)

            self.log(f"- User: {username} Deleted: {path_filename}")

        elif self.handle == FILE_ACTION_MODIFIED:
            if self.notification_enabled:
                event = self.handle   
                self.queue_notification(path_filename, event)

            self.log(f"! User: {username} Modified: {filename}")
            self.check_file(path_filename, filename)

        elif self.handle == FILE_RENAMED_FROM:
            self.old_name = filename

        elif self.handle == FILE_RENAMED_TO:
            self.log(f"User: {username} renamed: [{self.old_name}] to: [{filename}]")

        else:
            self.log(f"? Unknown action: {path_filename}")


    def check_file(self, path_filename, filename):
        if path_filename is None:
            return
        
        if os.path.isdir(path_filename):
            return

        try:            
            # self.processed_files.add(filename)
            self.dumper(path_filename)    
            self.check_hash(path_filename, filename)
                
        except Exception as e:
            self.log(f"Error during file checking\nFile: {path_filename}")
            

    def dumper(self, path_filename):
        self.contents = None
        with open(path_filename, "r", encoding="utf-8", errors="ignore") as f:
            self.contents = f.read()
            if len(self.contents) == 0:
                return


    def check_hash(self, path_filename, filename):
        # self.log(f"Checking hash {filename}")
        hash_thread = threading.Thread(target=self.compare_hashes, args=(path_filename, filename))
        hash_thread.start()
        hash_thread.join()
        # self.log("Scan complete\n")        


    def compare_hashes(self, path_filename, filename):
        # keys are file paths and values are the corresponding hash values in self.file_hashes

        try:
            sha256_hash = hashlib.sha256()

            # read in 64kb at a time
            with open(path_filename, "rb") as f:
                for block in iter(lambda: f.read(65536), b""):
                    sha256_hash.update(block)

            # self.log(f"SHA-256 HASH: {sha256_hash.hexdigest()}")
            hash_value = sha256_hash.hexdigest()

            # rename to new_file for easier code reading
            new_file = path_filename
            if hash_value in self.file_hashes.values():

                # get the filepath of the file corresponding with the matched hash value
                for matched_stored_file, stored_hash in self.file_hashes.items():
                    if matched_stored_file == new_file:
                        return
                    
                    if stored_hash == hash_value:
                        self.log(f"Files have the same hash: {hash_value}")
                        self.log(f"File: {matched_stored_file}")
                        self.log(f"File: {new_file}\n")
                        self.match_count += 1 
                        self.processed_files.add(new_file)

            else:
                # removing the old hash from the count if the file contents are changed
                if new_file in self.processed_files:
                        self.match_count -= 1
                        self.processed_files.remove(new_file)
                
                # storing hash of new contents
                # print(f"New file hashed: {new_file} - {hash_value}")
                self.file_hashes[new_file] = hash_value
              
        except:
            # self.log("File is unable to be hashed")
            pass


    def os_spider(self, path):
        # list all files and folders in the current directory and then submits all to a thread pool to be hashed
        # if its a directory it will recall it self to search that directory

        try:
            files = os.listdir(path)
            new_files = []

            for file in files:
                file_path = os.path.join(path, file)
                self.last_file = file
                self.file_count += 1

                # submit files to the thread pool
                if os.path.isfile(file_path):
                    add = self.threads.submit(self.check_file, file_path, file)
                    new_files.append(add)

                # submit directories to be searched
                # elif os.path.isdir(file_path):
                #     self.os_spider(file_path) 

                # wait for all files to be submited
                concurrent.futures.wait(new_files)

            # dont wait for all files
            # concurrent.futures.wait(new_files)
        
        except:
            pass

    def notfication(self, path_filename):
        print("CLICKED")
        os.startfile(path_filename)
        return True


    def main(self):
        if self.check_current_files is True:
            self.log("Checking for file duplicates...")
            self.log(f"Checking {self.path}\n")

            spider = threading.Thread(target=self.os_spider, args=(self.path,))
            spider.start()
            
            # block main logger from starting
            spider.join()
        

        # main logger
        self.log("Started file logging...")
        self.log(f"Started logging {self.path}\n")
        while 1:
            self.handle = self.get_handle()
            
            try:

                for self.handle, filename in self.get_changes():
                    if not self.is_running:
                        break

                    path_filename = os.path.join(self.path, filename)
                    filename = os.path.basename(path_filename)
                    self.last_file = filename
                    self.file_count += 1

                    username = self.get_username(path_filename)
                    self.monitor_handle(filename, path_filename, username)

                time.sleep(1) # -_- 

            except Exception as e:
                print(f"!! BIG Error during main runtime !!: {e}")

