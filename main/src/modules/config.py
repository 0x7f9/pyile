import os

STORED_PATHS = set()
PATHS = [
    # "C:\\Users\\dev\\AppData\\Local\\Temp"
    # "C:\\Users\\dev\\Documents"

    # add hard coded directories here
] 

class user_config:
    def __init__(self, log):
        self.log = log
        self.PATHS = PATHS
        self.config = {}
    
    
    def return_paths(self):
        return self.PATHS


    def config_location(self, cfg_name):
        path = os.path.join("main", "configs") 
        if not os.path.exists(path):
            os.makedirs(path)
        return os.path.join(path, cfg_name)


    def make_directories_config(self):
        cfg = self.config_location('saved_directories.cfg')
        self.log(f"Config file made - {cfg}")

        try:
            with open(cfg, "w") as file:
                file.write("[Saved Directories Config]\n\n")
                file.write("# Manually add directories as shown below\n")
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
            self.log("Error saving directories")


    def load_directories_config(self):
        self.log("Loading in saved directories...")
        cfg = self.config_location('saved_directories.cfg')
        
        try:
            with open(cfg, "r") as file:
                for line in file:
                    if line.startswith("-"):
                        path = line.strip().strip("-")
                        if path not in self.PATHS:
                            self.PATHS.append(path)

        except:
            self.log("No saved directories config found")
            self.make_directories_config()
            

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

