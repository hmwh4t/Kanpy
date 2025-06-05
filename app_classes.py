import os
import json
# import easygui # Removed easygui dependency
import datetime
import shutil
# import time # Potentially needed if you implement timestamped backups for corrupted files

# --- Constants ---
CENTRAL_CONFIG_PARENT_DIR = ""  # Main config file will be in the current directory
CONFIG_FILE_NAME = "workspaces.json"    # Name of the main config file (basename)
WORKSPACE_DATA_FILE_NAME = "workspace_data.json"
MAX_PASSWORD_ATTEMPTS = 3

# Directory where individual workspace folders will be created by default in tests
INDIVIDUAL_WORKSPACES_DEFAULT_ROOT = "workspaces"


class workspace_manager:
    """
    Manages multiple workspaces, including their creation, loading, saving,
    and the configuration of available workspaces.
    """
    def __init__(self):
        """Initializes the workspace_manager."""
        # Path to the main configuration file (e.g., ./workspaces.json)
        if CENTRAL_CONFIG_PARENT_DIR:
            self.workspaces_file_path = os.path.join(CENTRAL_CONFIG_PARENT_DIR, CONFIG_FILE_NAME)
        else: # If parent dir is empty, config file is in current dir
            self.workspaces_file_path = CONFIG_FILE_NAME
        self.available_workspaces = {}  # Stores workspace_name: path_to_workspace_directory
        self.current_workspace_object = None  # Holds the currently loaded workspace object

    def _save_workspaces(self):
        """
        Saves the current state of available_workspaces (name: path mapping)
        to the JSON configuration file (e.g., ./workspaces.json).
        Ensures the parent directory for the configuration file exists if specified.
        """
        config_dir = os.path.dirname(self.workspaces_file_path)
        try:
            if config_dir: # Ensure config_dir is not empty (e.g. if it's not current dir)
                os.makedirs(config_dir, exist_ok=True)
        except OSError as e:
            self._notify(f"Error creating configuration directory {config_dir}: {e}")
            return # Cannot save if directory creation fails

        try:
            with open(self.workspaces_file_path, "w", encoding="utf-8") as f:
                json.dump(self.available_workspaces, f, indent=4)
        except IOError as e:
            self._notify(f"Error saving workspaces file {self.workspaces_file_path}: {e}")

    def _notify(self, message):
        """Prints a message to the terminal."""
        print(message)

    def load_workspaces(self):
        """
        Loads workspace configurations from the JSON file (e.g., ./workspaces.json).
        - Creates an empty file (and its parent directory if needed) if it doesn't exist
          upon first save attempt if no workspaces are loaded.
        - Handles corrupted or improperly formatted files by starting fresh.
        - Cleans up entries for workspaces whose paths no longer exist or are invalid.
        - Returns the dictionary of available workspaces. An empty dictionary is
          returned if no workspaces are found or if issues occurred.
        """
        initial_file_exists = os.path.exists(self.workspaces_file_path)
        file_was_problematic = False  # Flag for existing files that were empty, corrupt, or ill-formatted

        if initial_file_exists:
            try:
                with open(self.workspaces_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if not content.strip(): # File is empty or only whitespace
                        self.available_workspaces = {}
                        file_was_problematic = True
                        self._notify(f"{self.workspaces_file_path} was empty. Initializing fresh.")
                    else:
                        loaded_data = json.loads(content)
                        if isinstance(loaded_data, dict):
                            self.available_workspaces = loaded_data
                        else: # Valid JSON, but not a dictionary as expected
                            self.available_workspaces = {}
                            file_was_problematic = True
                            self._notify(f"{self.workspaces_file_path} did not contain a valid workspace structure (expected a dictionary). Starting fresh.")
            except json.JSONDecodeError:
                self.available_workspaces = {}
                file_was_problematic = True
                self._notify(f"{self.workspaces_file_path} is corrupted or improperly formatted. Starting fresh.")
                # Optional: Backup corrupted file (consider uncommenting 'import time' if using timestamp)
                # try:
                #     timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                #     os.rename(self.workspaces_file_path, f"{self.workspaces_file_path}.corrupted_{timestamp}")
                # except OSError as e_mv:
                #     self._notify(f"Could not back up corrupted file: {e_mv}")
            except IOError as e: # Catch other potential IO errors like permission issues
                self.available_workspaces = {}
                file_was_problematic = True
                self._notify(f"An I/O error occurred while loading {self.workspaces_file_path}: {e}. Starting fresh.")
            except Exception as e: # Catch other unexpected errors
                self.available_workspaces = {}
                file_was_problematic = True
                self._notify(f"An unexpected error occurred while loading {self.workspaces_file_path}: {e}. Starting fresh.")
        else: # File does not exist
            self.available_workspaces = {}
            self._notify(f"{self.workspaces_file_path} not found. A new one will be created if workspaces are added.")

        # Clean up entries with missing paths or invalid path types
        workspaces_cleaned = False
        if self.available_workspaces:
            # Iterate over a copy of items for safe deletion
            for name, path_val in list(self.available_workspaces.items()):
                if not isinstance(path_val, str) or not os.path.exists(path_val):
                    if name in self.available_workspaces: # Ensure key still exists before deleting
                        del self.available_workspaces[name]
                    self._notify(f"Path for workspace '{name}' ('{str(path_val)}') not found or invalid. Entry removed.")
                    workspaces_cleaned = True
        
        # Save if the file was newly created (and its dir), problematic, or cleaned
        if not initial_file_exists or file_was_problematic or workspaces_cleaned:
            self._save_workspaces() # This will create the dir if it doesn't exist
            if not initial_file_exists and not self.available_workspaces and not workspaces_cleaned:
                # This message is for a completely fresh start where the file didn't exist and no workspaces were loaded/cleaned
                print(f"Initialized empty {self.workspaces_file_path}.")
            elif file_was_problematic and not self.available_workspaces and not workspaces_cleaned:
                 # This message is for when an existing file was problematic and resulted in an empty workspace list
                 print(f"Re-initialized {self.workspaces_file_path} as empty due to prior issues.")
            
        return self.available_workspaces

    def create_workspace(self, name: str, parent_path: str):
        """
        Creates a new workspace:
        1. Validates name and parent path.
        2. Checks for existing workspace with the same name or path.
        3. Creates a directory for the workspace within the given parent_path.
        4. Initializes a workspace_data.json file within it.
        5. Adds the new workspace to the available_workspaces configuration and saves it.
        Returns the created workspace object on success, None otherwise.
        """
        if not name or not isinstance(name, str) or not name.strip():
            self._notify("Workspace name must be a non-empty string.")
            return None
        name = name.strip() # Use the stripped name

        # Ensure the parent_path itself exists before trying to create a workspace in it.
        # The os.makedirs below will create the *workspace specific* directory.
        if not parent_path or not isinstance(parent_path, str): # Allow parent_path to be "" for current dir
             self._notify("Parent path for workspace must be a string.")
             return None
        if parent_path and not os.path.isdir(parent_path): # If parent_path is specified and not a dir
            self._notify(f"Parent path '{parent_path}' must be a valid existing directory.")
            return None
        # If parent_path is "" or ".", os.path.join will handle it correctly.

        if name in self.available_workspaces:
            self._notify(f"A workspace named '{name}' already exists in configuration (path: '{self.available_workspaces[name]}').")
            return None

        # Construct the full path for the new workspace directory
        # e.g., if parent_path is "workspaces" and name is "MyWS", path is "workspaces/MyWS"
        workspace_path = os.path.join(parent_path, name)
        workspace_data_file = os.path.join(workspace_path, WORKSPACE_DATA_FILE_NAME)

        if os.path.exists(workspace_path):
            self._notify(f"A file or directory already exists at '{workspace_path}'. Cannot create workspace.")
            return None
        
        try:
            os.makedirs(workspace_path) # Create the workspace directory (e.g., ./workspaces/MyWS/)
            
            # Create a new workspace object (which includes a default board)
            new_ws_obj = workspace(name=name) # Uses default board, current time
            
            # Save its data to its specific workspace_data.json
            with open(workspace_data_file, "w", encoding="utf-8") as f:
                json.dump(new_ws_obj.to_dict(), f, indent=4)

            # Add to the central list of workspaces and save that list
            # The path stored is relative to where workspaces.json is, e.g., "workspaces/MyWS"
            self.available_workspaces[name] = workspace_path
            self._save_workspaces()
            self._notify(f"Workspace '{name}' created successfully at '{workspace_path}'.")
            return new_ws_obj
        except OSError as e:
            self._notify(f"Error creating directory or file for workspace '{name}' at '{workspace_path}': {e}")
            # Attempt cleanup if partial creation occurred
            if os.path.exists(workspace_path):
                try:
                    if os.path.exists(workspace_data_file):
                        os.remove(workspace_data_file)
                    os.rmdir(workspace_path) # Remove directory if empty
                except OSError as cleanup_e:
                    self._notify(f"Error during cleanup of partially created workspace: {cleanup_e}")
            return None
        except Exception as e: 
            self._notify(f"An unexpected error occurred during workspace creation: {e}")
            return None

    def open_workspace(self, name_to_open: str):
        """
        Opens a workspace by loading its data from its workspace_data.json file.
        - Checks if the workspace exists in the configuration.
        - Checks if the workspace_data.json file exists.
        - Handles password checking if a password is set for the workspace.
        Returns the workspace object if successful, None otherwise.
        Sets self.current_workspace_object on success.
        """
        if name_to_open not in self.available_workspaces:
            self._notify(f"Workspace '{name_to_open}' not found in configuration.")
            return None

        workspace_path = self.available_workspaces[name_to_open] # e.g., "workspaces/MyWS"
        workspace_data_file = os.path.join(workspace_path, WORKSPACE_DATA_FILE_NAME) # e.g., "workspaces/MyWS/workspace_data.json"

        if not os.path.exists(workspace_data_file):
            self._notify(f"Workspace data file not found for '{name_to_open}' at '{workspace_data_file}'.")
            # Optional: Consider removing from available_workspaces if data file is missing
            # del self.available_workspaces[name_to_open]
            # self._save_workspaces()
            return None

        try:
            with open(workspace_data_file, "r", encoding="utf-8") as f:
                data = json.load(f) # Load data from workspace_data.json
            
            ws_obj = workspace.from_dict(data) # Create workspace object from data

            # Password check
            if ws_obj._pwd: # If a password is set for this workspace
                attempt_count = 0
                while attempt_count < MAX_PASSWORD_ATTEMPTS:
                    # Prompt for password in the terminal
                    password_attempt = input(
                        f"Enter password for workspace '{ws_obj.name}': (Attempt {attempt_count + 1}/{MAX_PASSWORD_ATTEMPTS})\n"
                        f"(Type 'CANCEL' (all caps) to abort): "
                    )
                    if password_attempt == "CANCEL": # User chose to cancel
                        self._notify("Password entry cancelled by user.")
                        return None
                    
                    if ws_obj.check_pwd(password_attempt):
                        self.current_workspace_object = ws_obj
                        self._notify(f"Workspace '{ws_obj.name}' opened successfully.")
                        return ws_obj
                    else:
                        attempt_count += 1
                        if attempt_count < MAX_PASSWORD_ATTEMPTS:
                            self._notify(f"Incorrect password. {MAX_PASSWORD_ATTEMPTS - attempt_count} attempts remaining.")
                        else:
                            self._notify("Incorrect password. Maximum attempts reached.")
                            return None
            else: # No password set for this workspace
                self.current_workspace_object = ws_obj
                self._notify(f"Workspace '{ws_obj.name}' opened successfully (no password).")
                return ws_obj

        except json.JSONDecodeError:
            self._notify(f"Error decoding data for workspace '{name_to_open}'. File '{workspace_data_file}' might be corrupt.")
            return None
        except IOError as e:
            self._notify(f"Error reading data file for workspace '{name_to_open}': {e}")
            return None
        except Exception as e: # Catch-all for other unexpected errors during opening
            self._notify(f"An unexpected error occurred while opening workspace '{name_to_open}': {e}")
            return None

    def save_current_workspace(self):
        """
        Saves the self.current_workspace_object (if one is open)
        back to its workspace_data.json file.
        Returns True on success, False otherwise.
        """
        if not self.current_workspace_object:
            self._notify("No workspace is currently open to save.")
            return False
        
        ws_obj = self.current_workspace_object
        # Ensure the workspace is still known to the manager (path lookup)
        if ws_obj.name not in self.available_workspaces:
            self._notify(f"Error: Current workspace '{ws_obj.name}' not found in manager's list. Cannot determine save path.")
            return False

        workspace_path = self.available_workspaces[ws_obj.name] # e.g., "workspaces/MyWS"
        workspace_data_file = os.path.join(workspace_path, WORKSPACE_DATA_FILE_NAME) # e.g., "workspaces/MyWS/workspace_data.json"

        try:
            # Ensure the directory for the workspace_data.json file exists
            # This is mostly a safeguard; it should exist if workspace was created/opened correctly.
            os.makedirs(workspace_path, exist_ok=True)
            with open(workspace_data_file, "w", encoding="utf-8") as f:
                json.dump(ws_obj.to_dict(), f, indent=4)
            self._notify(f"Workspace '{ws_obj.name}' saved successfully to '{workspace_data_file}'.")
            return True
        except IOError as e:
            self._notify(f"Error saving workspace '{ws_obj.name}': {e}")
            return False
        except Exception as e: # Catch-all for other unexpected errors during saving
            self._notify(f"An unexpected error occurred while saving workspace '{ws_obj.name}': {e}")
            return False

    def close_current_workspace(self):
        """Closes the currently open workspace, if any."""
        if self.current_workspace_object:
            self._notify(f"Closing workspace: {self.current_workspace_object.name}")
            self.current_workspace_object = None # Clear the current workspace
        else:
            self._notify("No workspace is currently open.")

# --- Minimal Board class for workspace to function ---
class Board:
    """
    Represents a board within a workspace.
    In a full application, this class would manage lists, cards, etc.
    """
    def __init__(self, name="Default Board", workspace_instance=None):
        """
        Initializes a Board.
        Args:
            name (str): The name of the board.
            workspace_instance (workspace, optional): A reference to the parent workspace.
        """
        self.name = name
        self.workspace = workspace_instance # Link to the parent workspace
        self.lists = []  # Placeholder for board content (e.g., lists of cards)
        # print(f"DEBUG: Board '{self.name}' initialized/linked for workspace '{workspace_instance.name if workspace_instance else 'None'}'.")

    def __str__(self):
        return f"Board(Name: '{self.name}', Lists: {len(self.lists)})"

    def to_dict(self):
        """
        Serializes the board object to a dictionary for storage.
        Minimal implementation; a real app would serialize lists, cards, etc.
        """
        return {"name": self.name, "lists_count": len(self.lists)} # Example data

    @classmethod
    def from_dict(cls, data: dict, workspace_instance=None):
        """
        Creates a Board object from a dictionary representation.
        Minimal implementation; a real app would deserialize lists, cards, etc.
        Args:
            data (dict): The dictionary containing board data.
            workspace_instance (workspace, optional): The parent workspace instance.
        """
        return cls(name=data.get("name", "Unnamed Board from data"), workspace_instance=workspace_instance)


class workspace:
    """
    Represents a single workspace, containing its metadata and a board.
    """
    def __init__(
        self,
        name: str,
        pwd=None, # Plain text password (INSECURE for production)
        last_edited=None, # datetime object or ISO string
        board_instance: Board = None,
    ):
        """
        Initializes a workspace.
        Args:
            name (str): The name of the workspace.
            pwd (str, optional): The password for the workspace.
                                 WARNING: Stored as plain text. Not for production.
                                 Defaults to None (no password).
            last_edited (datetime.datetime or str, optional):
                The last edited timestamp. If None, defaults to current UTC time.
                If a string, it's parsed as an ISO format datetime.
            board_instance (Board, optional): An existing Board object.
                                           If None, a new default Board is created.
        """
        self.name = name
        self._pwd = pwd  # Underscore suggests internal use; WARNING: plain text password

        # Handle last_edited timestamp
        if last_edited is None:
            self.last_edited = datetime.datetime.now(datetime.timezone.utc)
        elif isinstance(last_edited, str):
            try:
                self.last_edited = datetime.datetime.fromisoformat(last_edited)
            except ValueError:
                # Use print directly as workspace doesn't have _notify
                print(
                    f"Warning: last_edited string '{last_edited}' for workspace '{name}' "
                    f"is not in valid ISO format. Using current UTC time instead."
                )
                self.last_edited = datetime.datetime.now(datetime.timezone.utc)
        elif isinstance(last_edited, datetime.datetime):
            self.last_edited = last_edited
        else:
            print(
                f"Warning: Invalid type for last_edited ('{type(last_edited)}') for workspace '{name}'. "
                f"Using current UTC time instead."
            )
            self.last_edited = datetime.datetime.now(datetime.timezone.utc)

        # Handle the board for the workspace
        if board_instance is None:
            # Create a new default Board, linking it to this workspace instance
            self.board = Board(name=f"{self.name}'s Board", workspace_instance=self)
        else:
            self.board = board_instance
            # Ensure the provided board instance is linked to this workspace
            if hasattr(self.board, "workspace"):
                self.board.workspace = self
            # else: print(f"Warning: Provided board_instance for '{self.name}' does not have a 'workspace' attribute to link.")


    def check_pwd(self, password_attempt: str) -> bool:
        """
        Checks if the provided password attempt matches the workspace's password.
        WARNING: This is a placeholder using plain text comparison.
        In a real application, use proper password hashing (e.g., bcrypt, passlib).
        """
        if self._pwd is None: # No password set
            return True
        return self._pwd == password_attempt # Plain text comparison (INSECURE)

    def set_pwd(self, new_password: str, old_password_attempt: str = None) -> bool:
        """
        Sets or changes the workspace's password.
        WARNING: Stores new_password as plain text. HASH IT in a real app.
        Args:
            new_password (str): The new password. Empty string or None removes the password.
            old_password_attempt (str, optional): Current password, required if one is set.
        Returns:
            bool: True if password was set/changed, False otherwise.
        """
        if self._pwd is not None:  # If a password is currently set
            if old_password_attempt is None:
                print(
                    f"Error: Workspace '{self.name}' is password protected. "
                    f"Current password must be provided to change it."
                )
                return False
            if not self.check_pwd(old_password_attempt):
                print(
                    f"Error: Incorrect current password for workspace '{self.name}'. "
                    f"Password not changed."
                )
                return False

        # Store the new password (INSECURE: should be hashed)
        # Treat empty string as equivalent to None for removing password
        self._pwd = new_password if new_password else None
        
        if self._pwd:
            print(f"Password for workspace '{self.name}' has been updated.")
        else:
            print(f"Password for workspace '{self.name}' has been removed.")
        self.update_last_edited()  # Changing password is an edit
        return True

    def update_last_edited(self):
        """Updates the last_edited timestamp to the current UTC time."""
        self.last_edited = datetime.datetime.now(datetime.timezone.utc)
        # print(f"Workspace '{self.name}' last_edited timestamp updated to: {self.last_edited.isoformat()}")

    def get_board(self) -> Board:
        """Returns the Board object associated with this workspace."""
        return self.board

    def __str__(self) -> str:
        pwd_status = "Set" if self._pwd else "Not Set"
        board_info = str(self.board) if self.board else "No Board object"
        last_edited_str = (
            self.last_edited.isoformat()
            if isinstance(self.last_edited, datetime.datetime)
            else str(self.last_edited) # Fallback if not a datetime object
        )
        return (
            f"Workspace(Name: '{self.name}', Password Status: {pwd_status}, "
            f"Last Edited: {last_edited_str}, Board: [{board_info}])"
        )

    def to_dict(self) -> dict:
        """
        Serializes the workspace object to a dictionary for storage.
        WARNING: Includes plain text password if set.
        """
        board_data = (
            self.board.to_dict()
            if self.board and hasattr(self.board, "to_dict")
            else None
        )
        return {
            "name": self.name,
            "pwd": self._pwd, # WARNING: Storing plain text password
            "last_edited": self.last_edited.isoformat(),
            "board_data": board_data,
        }

    @classmethod
    def from_dict(cls, data: dict):
        """
        Creates a workspace object from a dictionary representation.
        Args:
            data (dict): The dictionary containing workspace data.
        """
        name = data.get("name", "Unnamed Workspace")
        pwd = data.get("pwd") # Password loaded as is (plain text)
        last_edited_str = data.get("last_edited") # Parsed by __init__

        board_data_from_dict = data.get("board_data")
        deserialized_board = None
        if board_data_from_dict:
            if hasattr(Board, "from_dict"):
                # workspace_instance will be set by the workspace's __init__ when it's passed
                deserialized_board = Board.from_dict(board_data_from_dict, workspace_instance=None)
            else: # Fallback if Board has no specific from_dict
                deserialized_board = Board(name=board_data_from_dict.get("name", "Default Board from Data"))
        
        # The workspace __init__ will handle:
        # - Parsing last_edited_str
        # - Using deserialized_board or creating a new default Board
        # - Linking the board to this new workspace instance
        return cls(
            name=name,
            pwd=pwd,
            last_edited=last_edited_str,
            board_instance=deserialized_board,
        )

def basic_test():
    """
    Runs a basic non-interactive test of the workspace manager functionality,
    printing output to the terminal.
    """
    print("--- Basic Test: Initializing Workspace Manager ---")
    wm = workspace_manager()
    # Main config file (workspaces.json) will be in the current directory
    print(f"Using main configuration file at: ./{wm.workspaces_file_path}")

    # Ensure the root directory for individual workspaces exists
    # This is where individual workspace folders like "BasicTestWorkspace_..." will be created.
    os.makedirs(INDIVIDUAL_WORKSPACES_DEFAULT_ROOT, exist_ok=True)
    print(f"Individual workspaces will be created under: ./{INDIVIDUAL_WORKSPACES_DEFAULT_ROOT}/")

    print("\n--- Basic Test: Loading Workspaces ---")
    # This will load from ./workspaces.json if it exists, or prepare for a new one.
    wm.load_workspaces()
    print(f"Initial available workspaces (names): {list(wm.available_workspaces.keys())}")

    timestamp_suffix = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    test_ws_name = f"BasicTestWorkspace_{timestamp_suffix}"
    # Individual workspaces will be created inside INDIVIDUAL_WORKSPACES_DEFAULT_ROOT
    test_ws_parent_dir_for_creation = INDIVIDUAL_WORKSPACES_DEFAULT_ROOT

    # Full path to the specific test workspace directory (e.g., ./workspaces/BasicTestWorkspace_...)
    full_test_ws_path = os.path.join(test_ws_parent_dir_for_creation, test_ws_name)

    # Clean up if this specific test workspace directory exists from a previous run
    if os.path.exists(full_test_ws_path):
        try:
            shutil.rmtree(full_test_ws_path)
            print(f"Cleaned up existing directory: {full_test_ws_path}")
            # Also remove from manager's list if it was there, then save config
            if test_ws_name in wm.available_workspaces:
                del wm.available_workspaces[test_ws_name]
                wm._save_workspaces() 
        except OSError as e:
            print(f"Warning: Could not clean up existing test directory {full_test_ws_path}: {e}")


    print(f"\n--- Basic Test: Creating Workspace '{test_ws_name}' in './{test_ws_parent_dir_for_creation}' ---")
    new_ws_obj = wm.create_workspace(test_ws_name, test_ws_parent_dir_for_creation)
    if new_ws_obj:
        print(f"Successfully created workspace: {new_ws_obj.name}")
        print(f"Workspace details: {new_ws_obj}")
        print(f"Available workspaces after creation (names): {list(wm.available_workspaces.keys())}")
        # Verify the path stored in available_workspaces
        expected_stored_path = os.path.join(test_ws_parent_dir_for_creation, test_ws_name)
        if wm.available_workspaces.get(test_ws_name) == expected_stored_path:
            print(f"Path stored in config for '{test_ws_name}': '{wm.available_workspaces[test_ws_name]}' (Correct)")
        else:
            print(f"Path stored in config for '{test_ws_name}': '{wm.available_workspaces.get(test_ws_name)}' (ERROR: Expected '{expected_stored_path}')")

    else:
        print(f"Failed to create workspace '{test_ws_name}'. Ending test.")
        return

    print(f"\n--- Basic Test: Opening Workspace '{test_ws_name}' ---")
    opened_ws_obj = wm.open_workspace(test_ws_name)
    if opened_ws_obj:
        print(f"Successfully opened workspace: {opened_ws_obj.name}")
        print(f"Current workspace in manager: {wm.current_workspace_object.name if wm.current_workspace_object else 'None'}")
        
        original_last_edited_time = opened_ws_obj.last_edited
        print(f"Original last_edited time: {original_last_edited_time.isoformat()}")

        print(f"\n--- Basic Test: Modifying current workspace '{opened_ws_obj.name}' (update_last_edited) ---")
        opened_ws_obj.update_last_edited()
        print(f"In-memory last_edited time updated to: {opened_ws_obj.last_edited.isoformat()}")
        assert wm.current_workspace_object.last_edited == opened_ws_obj.last_edited, "Manager's current object not updated!"

        print(f"\n--- Basic Test: Saving Current Workspace '{opened_ws_obj.name}' ---")
        save_success = wm.save_current_workspace()
        if save_success:
            print(f"Workspace '{opened_ws_obj.name}' saved successfully.")
        else:
            print(f"Failed to save workspace '{opened_ws_obj.name}'.")

        print(f"\n--- Basic Test: Closing Current Workspace '{opened_ws_obj.name}' ---")
        wm.close_current_workspace()
        print(f"Current workspace in manager after close: {wm.current_workspace_object.name if wm.current_workspace_object else 'None'}")

        print(f"\n--- Basic Test: Re-opening Workspace '{test_ws_name}' to check persistence ---")
        reopened_ws_obj = wm.open_workspace(test_ws_name)
        if reopened_ws_obj:
            print(f"Successfully re-opened workspace: {reopened_ws_obj.name}")
            print(f"Last edited time after re-open: {reopened_ws_obj.last_edited.isoformat()}")
            if reopened_ws_obj.last_edited > original_last_edited_time:
                print("SUCCESS: The last_edited time reflects the update made before saving.")
            else:
                print("NOTE: The last_edited time did not change as expected or was not later than original.")
                print(f"  Reopened: {reopened_ws_obj.last_edited.isoformat()}, Original: {original_last_edited_time.isoformat()}")

            print(f"\n--- Basic Test: Setting password for '{reopened_ws_obj.name}' ---")
            set_pwd_success = reopened_ws_obj.set_pwd("testpass123")
            assert set_pwd_success, "Failed to set initial password"
            wm.save_current_workspace() 
            wm.close_current_workspace()

            print(f"\n--- Basic Test: Re-opening '{reopened_ws_obj.name}' with password prompt ---")
            print("You will be prompted for a password. Enter 'testpass123'.")
            final_reopened_ws = wm.open_workspace(reopened_ws_obj.name)
            if final_reopened_ws:
                print(f"Successfully reopened '{final_reopened_ws.name}' after password entry.")
                wm.close_current_workspace()
            else:
                print(f"Failed to reopen '{reopened_ws_obj.name}' with password. Check terminal for prompts.")
        else:
            print(f"Failed to re-open workspace '{test_ws_name}'.")
    else:
        print(f"Failed to open workspace '{test_ws_name}' after creation. Some tests skipped.")
    
    print("\n--- Basic Test Completed ---")
    print(f"Reminder: Individual workspace folder '{full_test_ws_path}' (inside ./{INDIVIDUAL_WORKSPACES_DEFAULT_ROOT}/)")
    print(f"and the main configuration file './{wm.workspaces_file_path}' may exist.")
    print("Consider manual cleanup or adding automated cleanup to the test if needed.")

if __name__ == "__main__":
    basic_test()
