import os
import json
import easygui
class workspace_manager:
    # init workspace manager with available_workspaces, and current_workspace
    def __init__(self):
        self.available_workspaces = ""
        self.current_workspace = ""
    
    # load workspaces from json file
    def load_workspaces(self):
        if os.path.exists("workspaces.json"):
            with open("workspaces.json", "r") as f:
                self.available_workspaces = json.load(f)
        else:
            self.available_workspaces = {}
        # check if workspaces.json is empty
        if not self.available_workspaces:
            print("No workspaces found. Please add a workspace.")
            return False
        else:
            return True

def test():
    # create a workspace manager object
    wm = workspace_manager()
    # Folder selection
    folder_path = easygui.diropenbox(title="Please select a directory")   
