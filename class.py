import os
import json
import easygui
# import time # Potentially needed if you implement timestamped backups for corrupted files

class workspace_manager:
    def __init__(self):
        self.workspaces_file = "workspaces.json"
        self.available_workspaces = {}
        self.current_workspace = "" # This attribute is not used in the selected code

    def _save_workspaces(self):
        """Saves the current state of available_workspaces to the JSON file."""
        with open(self.workspaces_file, "w") as f:
            json.dump(self.available_workspaces, f, indent=4)

    def _notify(self, message, use_gui=True):
        """Prints a message and optionally shows it in an easygui msgbox."""
        print(message)
        if use_gui:
            easygui.msgbox(message)

    def load_workspaces(self):
        """
        Loads workspaces from the JSON file.
        Creates an empty file if it doesn't exist or if the existing one is invalid.
        Cleans up entries with missing paths.
        Returns True if workspaces are available after loading and cleaning, False otherwise.
        """
        initial_file_exists = os.path.exists(self.workspaces_file)
        file_was_problematic = False  # Flag for existing files that were empty, corrupt, or ill-formatted

        if initial_file_exists:
            try:
                with open(self.workspaces_file, "r") as f:
                    content = f.read()
                    if not content.strip(): # File is empty or only whitespace
                        self.available_workspaces = {}
                        file_was_problematic = True 
                    else:
                        loaded_data = json.loads(content)
                        if isinstance(loaded_data, dict):
                            self.available_workspaces = loaded_data
                        else: # Valid JSON, but not a dictionary
                            self.available_workspaces = {}
                            file_was_problematic = True
                            self._notify(f"{self.workspaces_file} did not contain a valid workspace structure (expected a dictionary). Starting fresh.", use_gui=False)
            except json.JSONDecodeError:
                self.available_workspaces = {}
                file_was_problematic = True
                self._notify(f"{self.workspaces_file} is corrupted or improperly formatted. Starting fresh.", use_gui=False)
                # Optional: Backup corrupted file:
                # try:
                #     os.rename(self.workspaces_file, self.workspaces_file + f".corrupted_{int(time.time())}")
                # except OSError as e_mv:
                #     self._notify(f"Could not back up corrupted file: {e_mv}", use_gui=False)
            except Exception as e: # Catch other potential IO errors
                self.available_workspaces = {}
                file_was_problematic = True
                self._notify(f"An unexpected error occurred while loading {self.workspaces_file}: {e}. Starting fresh.", use_gui=False)
        else: # File does not exist
            self.available_workspaces = {}

        # Clean up entries with missing paths
        workspaces_cleaned = False
        for name, path_val in list(self.available_workspaces.items()): # Iterate over a copy
            if not os.path.exists(path_val):
                del self.available_workspaces[name]
                self._notify(f"Path for workspace '{name}' ('{path_val}') not found. Entry removed.", use_gui=True)
                workspaces_cleaned = True
        
        # Save if:
        # 1. The file didn't exist initially (it's now created, possibly empty).
        # 2. Workspaces were cleaned from an existing file.
        # 3. An existing file was problematic (empty, corrupt, wrong format) and is now standardized (e.g. to {}).
        if not initial_file_exists or workspaces_cleaned or file_was_problematic:
            self._save_workspaces()
            if not initial_file_exists and not self.available_workspaces and not workspaces_cleaned:
                print(f"Initialized empty {self.workspaces_file}.")
            elif file_was_problematic and not self.available_workspaces and not workspaces_cleaned:
                 print(f"Re-initialized {self.workspaces_file} as empty due to prior issues.")
            
        return bool(self.available_workspaces)

    def create_workspace(self, name, parent_path):
        """Creates a new workspace directory and adds it to the configuration."""
        # Validate inputs
        if not name or not isinstance(name, str) or not name.strip():
            self._notify("Workspace name must be a non-empty string.")
            return
        name = name.strip()

        if not parent_path or not isinstance(parent_path, str) or not os.path.isdir(parent_path):
             self._notify("Parent path must be a valid existing directory.")
             return

        if name in self.available_workspaces:
            self._notify(f"A workspace named '{name}' already exists in configuration (path: '{self.available_workspaces[name]}').")
            return

        workspace_path = os.path.join(parent_path, name)

        if os.path.exists(workspace_path):
            self._notify(f"A file or directory already exists at '{workspace_path}'. Cannot create workspace.")
            return
        
        try:
            os.makedirs(workspace_path)
            self.available_workspaces[name] = workspace_path
            self._save_workspaces()
            self._notify(f"Workspace '{name}' created successfully at '{workspace_path}'.")
        except OSError as e:
            self._notify(f"Error creating directory for workspace '{name}' at '{workspace_path}': {e}")

    def open_workspace(self, name):
        # Placeholder for opening a workspace
        if name in self.available_workspaces:
            # Logic to open workspace, e.g., set self.current_workspace
            # os.chdir(self.available_workspaces[name]) or similar
            self._notify(f"Workspace '{name}' would be opened here (path: {self.available_workspaces[name]}).", use_gui=False)
        else:
            self._notify(f"Workspace '{name}' not found in configuration.", use_gui=True)


def test():
    wm = workspace_manager()
    
    if wm.load_workspaces():
        print(f"Successfully loaded {len(wm.available_workspaces)} workspace(s).")
    else:
        # load_workspaces handles specific file issue notifications.
        # This message indicates no usable workspaces are configured.
        print("No active workspaces found. You can create one using the prompts.")
    
    # Prompt for new workspace creation
    name_input = easygui.enterbox(msg="Enter the name for the new workspace:", title="Create Workspace")
    if name_input is None: # User pressed Cancel
        print("Workspace creation cancelled by user (name input).")
        return # Exit test function
    
    path_input = easygui.diropenbox(msg="Select the parent directory for the new workspace:", title="Create Workspace")
    if path_input is None: # User pressed Cancel
        print("Workspace creation cancelled by user (directory selection).")
        return # Exit test function

    # create_workspace method will handle validation and user notification for the inputs
    wm.create_workspace(name_input, path_input)

# To run the test:
test()