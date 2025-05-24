import os
import json
import easygui
import datetime
# import time # Potentially needed if you implement timestamped backups for corrupted files

class workspace_manager:
    def __init__(self):
        self.workspaces_file = "workspaces.json"
        self.available_workspaces = {} # Stores name: path
        self.current_workspace_object = None # Will hold the loaded workspace object

    def _save_workspaces(self):
        """Saves the current state of available_workspaces to the JSON file."""
        try:
            with open(self.workspaces_file, "w", encoding="utf-8") as f:
                json.dump(self.available_workspaces, f, indent=4)
        except IOError as e:
            self._notify(f"Error saving workspaces file {self.workspaces_file}: {e}", use_gui=True)


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
        Returns the dictionary of available workspaces. An empty dictionary is
        returned if no workspaces are found or if issues occurred.
        """
        initial_file_exists = os.path.exists(self.workspaces_file)
        file_was_problematic = False  # Flag for existing files that were empty, corrupt, or ill-formatted

        if initial_file_exists:
            try:
                with open(self.workspaces_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    if not content.strip(): # File is empty or only whitespace
                        self.available_workspaces = {}
                        file_was_problematic = True
                    else:
                        loaded_data = json.loads(content)
                        if isinstance(loaded_data, dict):
                            self.available_workspaces = loaded_data
                            # Removed early return here to ensure cleanup always runs
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
            except IOError as e: # Catch other potential IO errors like permission issues
                self.available_workspaces = {}
                file_was_problematic = True
                self._notify(f"An I/O error occurred while loading {self.workspaces_file}: {e}. Starting fresh.", use_gui=False)
            except Exception as e: # Catch other unexpected errors
                self.available_workspaces = {}
                file_was_problematic = True
                self._notify(f"An unexpected error occurred while loading {self.workspaces_file}: {e}. Starting fresh.", use_gui=False)
        else: # File does not exist
            self.available_workspaces = {}

        # Clean up entries with missing paths
        workspaces_cleaned = False
        if self.available_workspaces: # Only iterate if there's something to clean
            for name, path_val in list(self.available_workspaces.items()): # Iterate over a copy
                if not isinstance(path_val, str) or not os.path.exists(path_val): # Also check if path_val is a string
                    if name in self.available_workspaces: # Check if still exists
                        del self.available_workspaces[name]
                    self._notify(f"Path for workspace '{name}' ('{str(path_val)}') not found or invalid. Entry removed.", use_gui=True)
                    workspaces_cleaned = True
        
        if not initial_file_exists or workspaces_cleaned or file_was_problematic:
            self._save_workspaces() 
            if not initial_file_exists and not self.available_workspaces and not workspaces_cleaned:
                print(f"Initialized empty {self.workspaces_file}.")
            elif file_was_problematic and not self.available_workspaces and not workspaces_cleaned:
                 print(f"Re-initialized {self.workspaces_file} as empty due to prior issues.")
            
        return self.available_workspaces

# workspace_manager class modifications:

    def create_workspace(self, name, parent_path):
        """
        Creates a new workspace directory, initializes a workspace_data.json
        file within it, and adds it to the configuration.
        Returns the created workspace object on success, None otherwise.
        """
        if not name or not isinstance(name, str) or not name.strip():
            self._notify("Workspace name must be a non-empty string.")
            return None
        name = name.strip()

        if not parent_path or not isinstance(parent_path, str) or not os.path.isdir(parent_path):
            self._notify("Parent path must be a valid existing directory.")
            return None

        if name in self.available_workspaces:
            self._notify(f"A workspace named '{name}' already exists in configuration (path: '{self.available_workspaces[name]}').")
            return None

        workspace_path = os.path.join(parent_path, name)
        workspace_data_file = os.path.join(workspace_path, "workspace_data.json")

        if os.path.exists(workspace_path):
            self._notify(f"A file or directory already exists at '{workspace_path}'. Cannot create workspace.")
            return None
        
        try:
            os.makedirs(workspace_path)
            
            # Create a new workspace object
            new_ws_obj = workspace(name=name) # Uses default board, current time
            
            # Save its data to workspace_data.json
            with open(workspace_data_file, "w", encoding="utf-8") as f:
                json.dump(new_ws_obj.to_dict(), f, indent=4)

            self.available_workspaces[name] = workspace_path
            self._save_workspaces() # Save the main workspaces.json
            self._notify(f"Workspace '{name}' created successfully at '{workspace_path}'.")
            return new_ws_obj
        except OSError as e:
            self._notify(f"Error creating directory or file for workspace '{name}' at '{workspace_path}': {e}")
            if os.path.exists(workspace_path): # Cleanup if partial creation
                # More robust cleanup might be needed (e.g., remove file then dir)
                try:
                    if os.path.exists(workspace_data_file):
                        os.remove(workspace_data_file)
                    os.rmdir(workspace_path)
                except OSError:
                    pass # Best effort cleanup
            return None
        except Exception as e: 
            self._notify(f"An unexpected error occurred during workspace creation: {e}")
            return None


    def open_workspace(self, name_to_open: str):
        """
        Opens a workspace by loading its data from workspace_data.json.
        Handles password checking.
        Returns the workspace object if successful, None otherwise.
        Sets self.current_workspace_object.
        """
        if name_to_open not in self.available_workspaces:
            self._notify(f"Workspace '{name_to_open}' not found in configuration.", use_gui=True)
            return None

        workspace_path = self.available_workspaces[name_to_open]
        workspace_data_file = os.path.join(workspace_path, "workspace_data.json")

        if not os.path.exists(workspace_data_file):
            self._notify(f"Workspace data file not found for '{name_to_open}' at '{workspace_data_file}'.", use_gui=True)
            # Optionally, you could offer to create a default one here
            return None

        try:
            with open(workspace_data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            ws_obj = workspace.from_dict(data)

            # Password check
            if ws_obj._pwd: # If password is set
                attempt_count = 0
                max_attempts = 3
                while attempt_count < max_attempts:
                    password_attempt = easygui.passwordbox(
                        msg=f"Enter password for workspace '{ws_obj.name}':\n(Attempt {attempt_count + 1}/{max_attempts})",
                        title="Password Required"
                    )
                    if password_attempt is None: # User cancelled
                        self._notify("Password entry cancelled.", use_gui=False)
                        return None
                    if ws_obj.check_pwd(password_attempt):
                        self.current_workspace_object = ws_obj
                        self._notify(f"Workspace '{ws_obj.name}' opened successfully.", use_gui=False)
                        return ws_obj
                    else:
                        attempt_count += 1
                        if attempt_count < max_attempts:
                            easygui.msgbox(f"Incorrect password. {max_attempts - attempt_count} attempts remaining.", title="Error")
                        else:
                            self._notify("Incorrect password. Maximum attempts reached.", use_gui=True)
                            return None
            else: # No password set
                self.current_workspace_object = ws_obj
                self._notify(f"Workspace '{ws_obj.name}' opened successfully (no password).", use_gui=False)
                return ws_obj

        except json.JSONDecodeError:
            self._notify(f"Error decoding data for workspace '{name_to_open}'. File might be corrupt.", use_gui=True)
            return None
        except IOError as e:
            self._notify(f"Error reading data file for workspace '{name_to_open}': {e}", use_gui=True)
            return None
        except Exception as e:
            self._notify(f"An unexpected error occurred while opening workspace '{name_to_open}': {e}", use_gui=True)
            return None

    def save_current_workspace(self):
        """Saves the self.current_workspace_object back to its file."""
        if not self.current_workspace_object:
            self._notify("No workspace is currently open to save.", use_gui=False)
            return False
        
        ws_obj = self.current_workspace_object
        if ws_obj.name not in self.available_workspaces:
            self._notify(f"Error: Current workspace '{ws_obj.name}' not found in manager's list. Cannot determine save path.", use_gui=True)
            return False

        workspace_path = self.available_workspaces[ws_obj.name]
        workspace_data_file = os.path.join(workspace_path, "workspace_data.json")

        try:
            with open(workspace_data_file, "w", encoding="utf-8") as f:
                json.dump(ws_obj.to_dict(), f, indent=4)
            self._notify(f"Workspace '{ws_obj.name}' saved successfully.", use_gui=False)
            return True
        except IOError as e:
            self._notify(f"Error saving workspace '{ws_obj.name}': {e}", use_gui=True)
            return False
        except Exception as e:
            self._notify(f"An unexpected error occurred while saving workspace '{ws_obj.name}': {e}", use_gui=True)
            return False

    def close_current_workspace(self):
        if self.current_workspace_object:
            self._notify(f"Closing workspace: {self.current_workspace_object.name}", use_gui=False)
            self.current_workspace_object = None
        else:
            self._notify("No workspace is currently open.", use_gui=False)

# --- Minimal Board class for workspace to function ---
# In a full application, this Board class would be much more detailed,
# with its own methods for managing lists, cards, etc., and its own
# to_dict/from_dict methods for serialization.
class Board:
    def __init__(self, name="Default Board", workspace_instance=None):
        self.name = name
        # A reference to the parent workspace can be useful for navigation
        # or for operations like updating the workspace's last_edited timestamp.
        self.workspace = workspace_instance
        self.lists = []  # Placeholder for actual board content (lists of cards)
        # print(f"DEBUG: Board '{self.name}' initialized/linked for workspace '{workspace_instance.name if workspace_instance else 'None'}'.")

    def __str__(self):
        return f"Board(Name: '{self.name}', Lists: {len(self.lists)})"

    def to_dict(self):
        """Minimal serialization for the board."""
        # In a real app, this would serialize lists, cards, etc.
        return {"name": self.name, "lists_count": len(self.lists)}

    @classmethod
    def from_dict(cls, data, workspace_instance=None):
        """Minimal deserialization for the board."""
        # In a real app, this would deserialize lists, cards, etc.
        return cls(name=data.get("name", "Unnamed Board from data"), workspace_instance=workspace_instance)


class workspace:
    def __init__(
        self,
        name: str,
        pwd=None,
        last_edited=None,
        board_instance: Board = None,
    ):
        """
        Initializes a workspace.

        Args:
            name (str): The name of the workspace.
            pwd (str, optional): The password for the workspace.
                                 In a real application, this should be stored hashed.
                                 Defaults to None (no password).
            last_edited (datetime.datetime or str, optional):
                The last edited timestamp.
                If None, defaults to the current UTC time.
                If a string, it's parsed as an ISO format datetime.
            board_instance (Board, optional): An existing Board object to associate
                                           with this workspace. If None, a new
                                           default Board is created and associated.
        """
        self.name = name
        self._pwd = pwd  # Underscore suggests it's for internal use / might be handled specially (e.g. hashing)

        # Handle last_edited timestamp
        if last_edited is None:
            self.last_edited = datetime.datetime.now(datetime.timezone.utc)
        elif isinstance(last_edited, str):
            try:
                # Attempt to parse from ISO format string
                self.last_edited = datetime.datetime.fromisoformat(last_edited)
            except ValueError:
                self._notify(
                    f"Warning: last_edited string '{last_edited}' for workspace '{name}' "
                    f"is not in valid ISO format. Using current UTC time instead.",
                    use_gui=False
                )
                self.last_edited = datetime.datetime.now(
                    datetime.timezone.utc
                )
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
            # If no board is provided, create a new default Board.
            # The Board's __init__ should handle linking itself to this workspace.
            self.board = Board(
                name=f"{self.name}'s Board", workspace_instance=self
            )
        else:
            self.board = board_instance
            # If an existing board is provided, ensure its 'workspace' attribute
            # points to this workspace instance.
            if hasattr(self.board, "workspace"):
                if self.board.workspace != self:
                    self.board.workspace = self
            # If board_instance doesn't have a 'workspace' attribute, we can't set it.
            # This depends on the Board class design.

    def check_pwd(self, password_attempt: str) -> bool:
        """
        Checks if the provided password attempt matches the workspace's password.
        IMPORTANT: This is a placeholder. In a real application, you MUST use
        proper password hashing (e.g., with libraries like passlib or bcrypt)
        and compare hashes, not plain text passwords.
        """
        if self._pwd is None:
            return True  # No password set, so access is granted
        # Plain text comparison - DO NOT USE IN PRODUCTION
        return self._pwd == password_attempt

    def set_pwd(
        self, new_password: str, old_password_attempt: str = None
    ) -> bool:
        """
        Sets or changes the workspace's password.
        IMPORTANT: This is a placeholder. In a real application, new_password
        should be hashed before being stored.

        Args:
            new_password (str): The new password to set.
            old_password_attempt (str, optional): The current password.
                Required if a password is already set and needs to be changed.

        Returns:
            bool: True if the password was successfully set/changed, False otherwise.
        """
        if self._pwd is not None:  # If a password is already set
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

        # Store the new password (in a real app, HASH IT FIRST!)
        self._pwd = new_password
        print(f"Password for workspace '{self.name}' has been updated.")
        self.update_last_edited()  # Changing password is an edit
        return True

    def update_last_edited(self):
        """Updates the last_edited timestamp to the current UTC time."""
        self.last_edited = datetime.datetime.now(datetime.timezone.utc)
        # You might want to print a confirmation or log this:
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
            else str(self.last_edited)
        )

        return (
            f"Workspace(Name: '{self.name}', Password Status: {pwd_status}, "
            f"Last Edited: {last_edited_str}, Board: [{board_info}])"
        )

    # --- Methods for saving/loading this workspace object's state ---
    # These would typically be part of a more comprehensive save/load strategy,
    # potentially orchestrated by your WorkspaceManager.

    def to_dict(self) -> dict:
        """
        Serializes the workspace object to a dictionary.
        This is a basic representation. A full implementation would handle
        the board's data more thoroughly.
        """
        board_data = (
            self.board.to_dict()
            if self.board and hasattr(self.board, "to_dict")
            else None
        )
        return {
            "name": self.name,
            # WARNING: Storing plain text passwords, even in an intermediate dict, is insecure.
            # Consider omitting or handling securely if this dict is written to disk.
            "pwd": self._pwd,
            "last_edited": self.last_edited.isoformat(),
            "board_data": board_data, # Changed key to avoid confusion with board_instance
        }

    @classmethod
    def from_dict(cls, data: dict):
        """
        Creates a workspace object from a dictionary representation.
        This is a basic representation. A full implementation would handle
        the board's data more thoroughly.
        """
        name = data.get("name", "Unnamed Workspace")
        pwd = data.get("pwd") # Password will be stored as is from the dict
        last_edited_str = data.get("last_edited") # Parsed by __init__

        board_data_from_dict = data.get("board_data")
        deserialized_board = None
        if board_data_from_dict:
            if hasattr(Board, "from_dict"):
                # The workspace_instance will be set by the workspace's __init__
                deserialized_board = Board.from_dict(board_data_from_dict, workspace_instance=None)
            else: # Fallback if Board has no specific from_dict
                deserialized_board = Board(name=board_data_from_dict.get("name", "Default Board from Data"))
        
        # The workspace __init__ will handle:
        # - Parsing last_edited_str
        # - Using deserialized_board if provided, or creating a new default Board
        # - Linking the board to this new workspace instance
        return cls(
            name=name,
            pwd=pwd,
            last_edited=last_edited_str,
            board_instance=deserialized_board,
        )

def main_test_application():
    wm = workspace_manager()
    wm.load_workspaces() # Load existing workspace configurations

    while True:
        if wm.current_workspace_object:
            ws_name = wm.current_workspace_object.name
            prompt = f"Current Workspace: {ws_name}\n\nChoose an action:"
            choices = [
                "View Current Workspace Details",
                "Update Last Edited Time",
                "Set/Change Password",
                "View Board Details",
                "Save Current Workspace",
                "Close Current Workspace",
                "---",
                "List All Workspaces",
                "Create New Workspace",
                "Open Another Workspace",
                "Exit",
            ]
        else:
            prompt = "No workspace open. Choose an action:"
            choices = [
                "List All Workspaces",
                "Create New Workspace",
                "Open Workspace",
                "Exit",
            ]

        action = easygui.buttonbox(prompt, title="Workspace Manager Test", choices=choices)

        if action is None or action == "Exit":
            if wm.current_workspace_object:
                save_on_exit = easygui.ynbox(f"Do you want to save changes to '{wm.current_workspace_object.name}' before exiting?", "Save on Exit")
                if save_on_exit:
                    wm.save_current_workspace()
            print("Exiting application.")
            break

        # --- Actions when a workspace IS open ---
        if wm.current_workspace_object:
            current_ws = wm.current_workspace_object
            if action == "View Current Workspace Details":
                easygui.msgbox(str(current_ws), title=f"Details for {current_ws.name}")
            elif action == "Update Last Edited Time":
                current_ws.update_last_edited()
                wm._notify(f"'{current_ws.name}' last_edited time updated.", use_gui=False)
                easygui.msgbox(f"Last edited time for '{current_ws.name}' updated.\nRemember to save.", title="Timestamp Updated")
            elif action == "Set/Change Password":
                old_pwd_attempt = None
                if current_ws._pwd:
                    old_pwd_attempt = easygui.passwordbox(f"Enter current password for '{current_ws.name}' to change it:", "Current Password")
                    if old_pwd_attempt is None: # User cancelled
                        continue
                
                new_pwd = easygui.passwordbox(f"Enter new password for '{current_ws.name}' (leave blank to remove password):", "New Password")
                if new_pwd is not None: # User didn't cancel new password input
                    if not new_pwd: new_pwd = None # Treat empty string as no password

                    if current_ws.set_pwd(new_pwd, old_pwd_attempt):
                        easygui.msgbox("Password updated successfully.\nRemember to save.", title="Password Set")
                    # set_pwd already prints errors via _notify if it fails
            elif action == "View Board Details":
                board = current_ws.get_board()
                easygui.msgbox(str(board), title=f"Board for {current_ws.name}")
            elif action == "Save Current Workspace":
                wm.save_current_workspace()
            elif action == "Close Current Workspace":
                if current_ws: # Should always be true here
                    save_on_close = easygui.ynbox(f"Do you want to save changes to '{current_ws.name}' before closing?", "Save Changes")
                    if save_on_close:
                        wm.save_current_workspace()
                wm.close_current_workspace()

        # --- Actions available whether a workspace is open or not ---
        if action == "List All Workspaces":
            if wm.available_workspaces:
                msg = "Available Workspaces:\n\n"
                for name, path in wm.available_workspaces.items():
                    msg += f"- {name}: {path}\n"
                easygui.msgbox(msg, title="Available Workspaces")
            else:
                easygui.msgbox("No workspaces configured yet.", title="Available Workspaces")

        elif action == "Create New Workspace":
            if wm.current_workspace_object:
                 save_before_create = easygui.ynbox(f"Do you want to save changes to '{wm.current_workspace_object.name}' before creating a new one?", "Save Changes")
                 if save_before_create:
                     wm.save_current_workspace()
                 wm.close_current_workspace()

            ws_name_input = easygui.enterbox("Enter name for the new workspace:", "Create Workspace")
            if ws_name_input:
                parent_dir_input = easygui.diropenbox("Select parent directory for the new workspace:", "Create Workspace")
                if parent_dir_input:
                    created_ws_obj = wm.create_workspace(ws_name_input, parent_dir_input)
                    if created_ws_obj:
                        # Optionally open it immediately
                        open_now = easygui.ynbox(f"Workspace '{created_ws_obj.name}' created. Open it now?", "Open Workspace")
                        if open_now:
                            wm.current_workspace_object = created_ws_obj # Already loaded by create_workspace
                            wm._notify(f"Workspace '{created_ws_obj.name}' is now open.", use_gui=False)

        elif action == "Open Workspace" or action == "Open Another Workspace":
            if wm.current_workspace_object and action == "Open Another Workspace":
                 save_before_open = easygui.ynbox(f"Do you want to save changes to '{wm.current_workspace_object.name}' before opening another?", "Save Changes")
                 if save_before_open:
                     wm.save_current_workspace()
                 wm.close_current_workspace()

            if not wm.available_workspaces:
                easygui.msgbox("No workspaces available to open. Please create one first.", "Open Workspace")
                continue
            
            chosen_ws_name = easygui.choicebox(
                "Select a workspace to open:",
                "Open Workspace",
                choices=list(wm.available_workspaces.keys())
            )
            if chosen_ws_name:
                wm.open_workspace(chosen_ws_name) # This will set wm.current_workspace_object on success

# To run the test application:
if __name__ == "__main__":
    # Make sure all class definitions (workspace_manager, Board, workspace) are above this point.
    main_test_application()

