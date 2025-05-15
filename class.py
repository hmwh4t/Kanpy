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
            return False
        else:
            return True
    
    def create_workspace(self, name, path):
        # check if workspace already exists
        if name in self.available_workspaces and self.available_workspaces[name] == path:
            easygui.msgbox(f"Workspace {name} already exists at {path}.")
            print(f"Workspace {name} already exists at {path}.")
        else:
            # cteate new folder path+name
            new_path = os.path.join(path, name)
            # check if folder already exists
            if os.path.exists(new_path):
                easygui.msgbox(f"Workspace {name} already exists at {new_path}.")
                print(f"Workspace {name} already exists at {new_path}.")
            else:
                # create new folder
                os.makedirs(new_path)
                # add workspace to workspaces.json
                self.available_workspaces[name] = new_path
                with open("workspaces.json", "w") as f:
                    json.dump(self.available_workspaces, f)
                easygui.msgbox(f"Workspace {name} created at {new_path}.")
                print(f"Workspace {name} created at {new_path}.")
    
    def open_workspace(self, name):
        # check if workspace exists
        pass

def test():
    # create a workspace manager object
    wm = workspace_manager()
    
    # Check if workspaces.json exists and load it if not show option to create a new one
    if not wm.load_workspaces():
        # create a new workspaces.json file
        with open("workspaces.json", "w") as f:
            json.dump({}, f)
        print("No workspaces found. Please add a workspace.")
    
    # # Create a new workspace
    name = easygui.enterbox("Enter workspace name:")
    path = easygui.diropenbox("Select workspace directory:")
    if name and path:
        wm.create_workspace(name, path)
    
    # Folder selection
    # folder_path = easygui.diropenbox(title="Please select a directory")
    
test()