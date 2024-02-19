import os

# STORED_PATHS = set()
PATHS = [
    # "C:\\Windows"
    # "C:\\Users\\dev\\Documents"

    # add hard coded directories here all will be loaded in on start up
] 

EXCLUDED_PATHS = [
    # when monitoring the entire C:\ drive it will detect all changes made in the system
    # adding file paths here will reduce unnecessary output logs
    # exluded paths can be a partial path or a full path

    # notfication triggers make a temp file in this location
    "\\AppData\\Local\\Microsoft\\Windows\\Explorer\\NotifyIcon",

    # when chrome is open it constantly writes user data here
    "\\AppData\\Local\\Google\\Chrome\\User Data\\Default"

    # add hard coded directories here all will be loaded in on start up
] 

class user_config:
    def __init__(self, log):
        self.log = log
        self.PATHS = PATHS
        self.EXCLUDE = EXCLUDED_PATHS
        self.config = {}
    
    
    def return_paths(self):
        return self.PATHS
    
    
    def return_excluded_paths(self):
        return self.EXCLUDE


    def config_location(self, cfg_name):
        # gets relative pathing and goes back three levels to find configs folder
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(script_dir, "configs")

        if not os.path.exists(path):
            os.makedirs(path)
        return os.path.join(path, cfg_name)


    def make_save_directories_config(self):
        cfg = self.config_location('saved_directories.cfg')
        self.log(f"Saved directories config file made  - {cfg}")

        try:
            with open(cfg, "w") as file:
                file.write("[Saved Directories Config]\n\n")
                file.write("# Manually add saved directories as shown below\n")
                file.write("# -C:\\Users\n")
                file.write("# -C:\\Users\\dev\\AppData\n")
                file.write("# -C:/Users/dev/AppData\n\n")
                
        except:
            self.log("Error making saved directories file")


    def save_directories_config(self, path):
        if path == None:
            return
        
        cfg = self.config_location('saved_directories.cfg')
        self.log(f"Path has been added to saved directories config - {path}")
        try:
            with open(cfg, "a") as file:
                file.write(f"-{path}\n")
        except:
            self.log("Error saving saved directories file")


    def load_directories_config(self):
        self.log("Loading in saved directories...")
        cfg = self.config_location('saved_directories.cfg')
        
        try:
            with open(cfg, "r") as file:
                for line in file:
                    if line.startswith("-"):
                        path = line.strip().strip("-")
                        if not os.path.exists(path):
                            self.log(f"Path {path} does not exists, please remove from saved config file")
                            continue 
                       
                        # load new paths in
                        if path not in self.PATHS:
                            self.PATHS.append(path)

        except:
            self.log("No saved directories config found")
            self.make_directories_config()


    def make_excluded_directories_config(self):
        cfg = self.config_location('excluded_directories.cfg')
        self.log(f"Exclude directories config file made - {cfg}")

        try:
            with open(cfg, "w") as file:
                file.write("[Excluded Directories Config]\n\n")
                file.write("# Manually add excluded directories as shown below\n")
                file.write("# Directories can be a partial path or a full path\n")
                file.write("# -C:\\Windows\n")
                file.write("# -\\AppData\n")
                file.write("# -\\dev\\AppData\n")
                file.write("# -C:/Users/dev/AppData\n\n")
                
        except:
            self.log("Error making excluded directories file")


    def save_excluded_directories_config(self, path):
        if path == None:
            return
        
        cfg = self.config_location('excluded_directories.cfg')
        self.log(f"Path has been added to excluded directories config - {path}")
        try:
            with open(cfg, "a") as file:
                file.write(f"-{path}\n")
        except:
            self.log("Error saving excluded directories file")


    def load_excluded_directories_config(self):
        self.log("Loading in excluded directories...")
        cfg = self.config_location('excluded_directories.cfg')
        
        try:
            with open(cfg, "r") as file:
                for line in file:
                    if line.startswith("-"):
                        path = line.strip().strip("-")
                       
                        # load new paths in
                        if path not in self.EXCLUDE:
                            self.EXCLUDE.append(path)

        except:
            self.log("No excluded directories config found")
            self.make_excluded_directories_config()
            

    def save_checkbox_config(self, checkbox_1_value, checkbox_2_value, checkbox_3_value, checkbox_4_value, checkbox_5_value):
        self.log("Saving checkbox states...")
        cfg =  self.config_location('checkbox_states.cfg')

        try:
            with open(cfg, 'w') as configfile:
                configfile.write(f"[Checkbox States Config]\n\n")
                configfile.write(f"Checkbox1 = {checkbox_1_value}\n")
                # configfile.write(f"Checkbox2 = {checkbox_2_value}\n")
                configfile.write(f"Checkbox3 = {checkbox_3_value}\n")
                configfile.write(f"Checkbox4 = {checkbox_4_value}\n")
                configfile.write(f"Checkbox5 = {checkbox_5_value}\n")
                
        except:
            self.log("Error saving checkbox states config")


    def load_checkbox_config(self):
        cfg = self.config_location('checkbox_states.cfg')
        if not os.path.exists(cfg):
            return

        self.log("Loading in checkboxes states...")
        try:
            with open(cfg, "r") as file:
                for line in file:
                    if line.startswith("Checkbox1 ="):
                        self.config["Checkbox1_value"] = line.split(" = ")[1].strip()
                    
                    elif line.startswith("Checkbox3 ="):    
                        self.config["Checkbox3_value"] = line.split(" = ")[1].strip()
                    
                    elif line.startswith("Checkbox4 ="):
                        self.config["Checkbox4_value"] = line.split(" = ")[1].strip()

                    elif line.startswith("Checkbox5 ="):
                        self.config["Checkbox5_value"] = line.split(" = ")[1].strip()

            return self.config
    
        except:
            self.log("Error loading checkboxes states config")

