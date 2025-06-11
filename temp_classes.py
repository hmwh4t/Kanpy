import os
import json
import easygui
import datetime
import uuid # Added for unique IDs
# import time # Potentially needed if you implement timestamped backups for corrupted files

# --- Card Class (Improved) ---
class Card():
    def __init__(self, name, description="None", card_id=None):
        self.card_id = card_id if card_id else self._generate_id()
        self.name = name
        self.description = description

    def _generate_id(self):
        return str(uuid.uuid4())

    def change_name(self, new_name):
        self.name = new_name
        # In a more complex app, this might notify a parent list/board to update workspace's last_edited

    def change_desc(self, new_description):
        self.description = new_description
        # Similarly, might notify parent

    def to_dict(self):
        return {
            "card_id": self.card_id,
            "name": self.name,
            "description": self.description
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            card_id=data.get("card_id"), # Load existing ID
            name=data.get("name", "Untitled Card"),
            description=data.get("description", "No description")
        )

    def __str__(self):
        return f"Card ID: {self.card_id[:8]}...\nName: {self.name}\nDescription: {self.description}"

# --- List Class (Improved) ---
class List():
    def __init__(self, list_name, description="None", list_id=None):
        self.list_id = list_id if list_id else self._generate_id()
        self.list_name = list_name
        self.description = description
        self.cards = []  # Stores Card objects

    def _generate_id(self):
        return str(uuid.uuid4())

    def change_name(self, new_name):
        self.list_name = new_name # Typo fixed
        # Might notify parent board

    def change_desc(self, new_description):
        self.description = new_description
        # Might notify parent board

    def create_card(self, name, description="None"):
        new_card = Card(name=name, description=description)
        self.cards.append(new_card)
        # Might notify parent board
        return new_card

    def add_card(self, card_object: Card):
        if not isinstance(card_object, Card):
            raise TypeError("Can only add Card objects to a List.")
        if not any(c.card_id == card_object.card_id for c in self.cards):
            self.cards.append(card_object)
        else:
            print(f"Warning: Card with ID {card_object.card_id} already in list '{self.list_name}'.")


    def remove_card(self, card_id_to_remove):
        initial_len = len(self.cards)
        self.cards = [card for card in self.cards if card.card_id != card_id_to_remove]
        # Might notify parent board if successful
        return len(self.cards) < initial_len

    def get_card(self, card_id_to_find):
        for card in self.cards:
            if card.card_id == card_id_to_find:
                return card
        return None

    def get_all_cards(self):
        return self.cards

    def to_dict(self):
        return {
            "list_id": self.list_id,
            "list_name": self.list_name,
            "description": self.description,
            "cards": [card.to_dict() for card in self.cards]
        }

    @classmethod
    def from_dict(cls, data):
        list_obj = cls(
            list_id=data.get("list_id"), # Load existing ID
            list_name=data.get("list_name", "Untitled List"),
            description=data.get("description", "No description")
        )
        card_data_list = data.get("cards", [])
        for card_data in card_data_list:
            list_obj.add_card(Card.from_dict(card_data))
        return list_obj

    def __str__(self):
        card_details = []
        for card in self.cards:
            card_details.append(f"  - Card: {card.name} (ID: {card.card_id[:8]}...)")
        cards_str = "\n".join(card_details) if card_details else "  No cards in this list."
        return f"List ID: {self.list_id[:8]}...\nName: {self.list_name}\nDescription: {self.description}\nCards ({len(self.cards)}):\n{cards_str}"


# --- Board Class (Modified for Lists and Cards) ---
class Board:
    def __init__(self, name="Default Board", workspace_instance=None, board_id=None):
        self.board_id = board_id if board_id else self._generate_id()
        self.name = name
        self.workspace = workspace_instance # Reference to parent workspace
        self.lists = []  # Stores List objects

    def _generate_id(self):
        return str(uuid.uuid4())
    
    def change_name(self, new_name):
        self.name = new_name
        # The workspace's last_edited will be updated on save by workspace_manager

    def add_list(self, list_object: List):
        if not isinstance(list_object, List):
            raise TypeError("Can only add List objects to a Board.")
        if not any(l.list_id == list_object.list_id for l in self.lists):
            self.lists.append(list_object)
        else:
            print(f"Warning: List with ID {list_object.list_id} already on board '{self.name}'.")


    def create_list(self, list_name, description="None"):
        new_list = List(list_name=list_name, description=description)
        self.add_list(new_list)
        # Workspace last_edited updated on save
        return new_list

    def remove_list(self, list_id_to_remove):
        initial_len = len(self.lists)
        self.lists = [lst for lst in self.lists if lst.list_id != list_id_to_remove]
        # Workspace last_edited updated on save if successful
        return len(self.lists) < initial_len

    def get_list(self, list_id_to_find):
        for lst in self.lists:
            if lst.list_id == list_id_to_find:
                return lst
        return None

    def get_all_lists(self):
        return self.lists

    def __str__(self):
        list_overviews = [f"  - List: '{l.list_name}' (ID: {l.list_id[:8]}..., {len(l.cards)} cards)" for l in self.lists]
        lists_str = "\n".join(list_overviews) if list_overviews else "  No lists on this board yet."
        return f"Board ID: {self.board_id[:8]}...\nName: '{self.name}'\nLists ({len(self.lists)}):\n{lists_str}"

    def to_dict(self):
        return {
            "board_id": self.board_id,
            "name": self.name,
            "lists": [lst.to_dict() for lst in self.lists]
        }

    @classmethod
    def from_dict(cls, data, workspace_instance=None):
        board_obj = cls(
            board_id=data.get("board_id"),
            name=data.get("name", "Unnamed Board from data"),
            workspace_instance=workspace_instance
        )
        list_data_list = data.get("lists", [])
        for list_data in list_data_list:
            board_obj.add_list(List.from_dict(list_data))
        return board_obj

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
        file_was_problematic = False

        if initial_file_exists:
            try:
                with open(self.workspaces_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    if not content.strip(): 
                        self.available_workspaces = {}
                        file_was_problematic = True
                    else:
                        loaded_data = json.loads(content)
                        if isinstance(loaded_data, dict):
                            self.available_workspaces = loaded_data
                        else: 
                            self.available_workspaces = {}
                            file_was_problematic = True
                            self._notify(f"{self.workspaces_file} did not contain a valid workspace structure (expected a dictionary). Starting fresh.", use_gui=False)
            except json.JSONDecodeError:
                self.available_workspaces = {}
                file_was_problematic = True
                self._notify(f"{self.workspaces_file} is corrupted or improperly formatted. Starting fresh.", use_gui=False)
            except IOError as e: 
                self.available_workspaces = {}
                file_was_problematic = True
                self._notify(f"An I/O error occurred while loading {self.workspaces_file}: {e}. Starting fresh.", use_gui=False)
            except Exception as e: 
                self.available_workspaces = {}
                file_was_problematic = True
                self._notify(f"An unexpected error occurred while loading {self.workspaces_file}: {e}. Starting fresh.", use_gui=False)
        else: 
            self.available_workspaces = {}

        workspaces_cleaned = False
        if self.available_workspaces: 
            for name, path_val in list(self.available_workspaces.items()): 
                if not isinstance(path_val, str) or not os.path.exists(path_val): 
                    if name in self.available_workspaces: 
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

    def create_workspace(self, name, parent_path):
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
            new_ws_obj = workspace(name=name) 
            
            with open(workspace_data_file, "w", encoding="utf-8") as f:
                json.dump(new_ws_obj.to_dict(), f, indent=4)

            self.available_workspaces[name] = workspace_path
            self._save_workspaces()
            self._notify(f"Workspace '{name}' created successfully at '{workspace_path}'.")
            return new_ws_obj
        except OSError as e:
            self._notify(f"Error creating directory or file for workspace '{name}' at '{workspace_path}': {e}")
            if os.path.exists(workspace_path): 
                try:
                    if os.path.exists(workspace_data_file):
                        os.remove(workspace_data_file)
                    os.rmdir(workspace_path)
                except OSError:
                    pass 
            return None
        except Exception as e: 
            self._notify(f"An unexpected error occurred during workspace creation: {e}")
            return None

    def open_workspace(self, name_to_open: str):
        if name_to_open not in self.available_workspaces:
            self._notify(f"Workspace '{name_to_open}' not found in configuration.", use_gui=True)
            return None

        workspace_path = self.available_workspaces[name_to_open]
        workspace_data_file = os.path.join(workspace_path, "workspace_data.json")

        if not os.path.exists(workspace_data_file):
            self._notify(f"Workspace data file not found for '{name_to_open}' at '{workspace_data_file}'.", use_gui=True)
            return None

        try:
            with open(workspace_data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            ws_obj = workspace.from_dict(data)

            if ws_obj._pwd: 
                attempt_count = 0
                max_attempts = 3
                while attempt_count < max_attempts:
                    password_attempt = easygui.passwordbox(
                        msg=f"Enter password for workspace '{ws_obj.name}':\n(Attempt {attempt_count + 1}/{max_attempts})",
                        title="Password Required"
                    )
                    if password_attempt is None: 
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
            else: 
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
        if not self.current_workspace_object:
            self._notify("No workspace is currently open to save.", use_gui=False)
            return False
        
        ws_obj = self.current_workspace_object
        # Update last_edited timestamp before saving
        ws_obj.update_last_edited()

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

class workspace:
    def __init__(
        self,
        name: str,
        pwd=None,
        last_edited=None,
        board_instance: Board = None,
    ):
        self.name = name
        self._pwd = pwd  

        if last_edited is None:
            self.last_edited = datetime.datetime.now(datetime.timezone.utc)
        elif isinstance(last_edited, str):
            try:
                self.last_edited = datetime.datetime.fromisoformat(last_edited)
            except ValueError:
                print( # Using print as _notify isn't available in class method context directly
                    f"Warning: last_edited string '{last_edited}' for workspace '{name}' "
                    f"is not in valid ISO format. Using current UTC time instead."
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

        if board_instance is None:
            self.board = Board(
                name=f"{self.name}'s Board", workspace_instance=self
            )
        else:
            self.board = board_instance
            if hasattr(self.board, "workspace"): # Ensure the board is linked to this workspace
                self.board.workspace = self
            else: # This case should ideally not happen if Board class is well-defined
                print(f"Warning: Board instance for workspace '{name}' does not have a 'workspace' attribute.")


    def check_pwd(self, password_attempt: str) -> bool:
        if self._pwd is None:
            return True  
        return self._pwd == password_attempt

    def set_pwd(
        self, new_password: str, old_password_attempt: str = None
    ) -> bool:
        if self._pwd is not None: 
            if old_password_attempt is None:
                easygui.msgbox( # Using easygui directly as it's a user-facing error
                    f"Error: Workspace '{self.name}' is password protected. "
                    f"Current password must be provided to change it."
                )
                return False
            if not self.check_pwd(old_password_attempt):
                easygui.msgbox(
                    f"Error: Incorrect current password for workspace '{self.name}'. "
                    f"Password not changed."
                )
                return False
        self._pwd = new_password if new_password else None # Store None if new_password is empty
        easygui.msgbox(f"Password for workspace '{self.name}' has been updated.")
        self.update_last_edited() 
        return True

    def update_last_edited(self):
        self.last_edited = datetime.datetime.now(datetime.timezone.utc)

    def get_board(self) -> Board:
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
            f"Last Edited: {last_edited_str}, Board: [\n{board_info}\n])" # Prettier board display
        )

    def to_dict(self) -> dict:
        board_data = (
            self.board.to_dict()
            if self.board and hasattr(self.board, "to_dict")
            else None
        )
        return {
            "name": self.name,
            "pwd": self._pwd,
            "last_edited": self.last_edited.isoformat(),
            "board_data": board_data, 
        }

    @classmethod
    def from_dict(cls, data: dict):
        name = data.get("name", "Unnamed Workspace")
        pwd = data.get("pwd") 
        last_edited_str = data.get("last_edited")

        board_data_from_dict = data.get("board_data")
        deserialized_board = None
        
        # Create the workspace object first, so 'self' (workspace_instance) is available for the board
        # The board will be properly linked in the __init__
        ws_obj = cls(name=name, pwd=pwd, last_edited=last_edited_str, board_instance=None)

        if board_data_from_dict:
            if hasattr(Board, "from_dict"):
                # Pass the newly created workspace object as workspace_instance
                deserialized_board = Board.from_dict(board_data_from_dict, workspace_instance=ws_obj)
                ws_obj.board = deserialized_board # Assign the fully deserialized board
            else: 
                # Fallback if Board has no specific from_dict (less likely with our structure)
                # This would create a new default board in ws_obj.__init__ if deserialized_board is None
                # Or use a minimally configured board if we did this:
                # deserialized_board = Board(name=board_data_from_dict.get("name", "Default Board from Data"), workspace_instance=ws_obj)
                # ws_obj.board = deserialized_board
                # For now, if from_dict exists, we use it. If not, __init__ handles it.
                 print(f"Warning: Board class does not have from_dict method. Board data may not be fully loaded for {name}.")
                 # ws_obj.board will remain the default one created in __init__ or will be None if board_instance was meant to be set
                 # The current structure of __init__ ensures a board is always present.

        # If deserialized_board is still None (e.g., no board_data or Board.from_dict failed somehow)
        # the __init__ of workspace would have already created a default board and linked it.
        # If deserialized_board was successfully created and assigned to ws_obj.board, 
        # the __init__ logic for board_instance would correctly use it and link it.
        return ws_obj


# --- Helper for UI ---
def safe_choicebox(msg, title, choices_dict):
    """
    choices_dict: A dictionary where keys are display strings and values are IDs.
    Returns the ID of the chosen item, or None.
    """
    if not choices_dict:
        easygui.msgbox(f"No items to choose from in {title}.", title)
        return None
    
    display_choices = list(choices_dict.keys())
    chosen_display_str = easygui.choicebox(msg, title, display_choices)
    
    if chosen_display_str:
        return choices_dict[chosen_display_str] # Return the ID
    return None

# --- Main Application UI (with Board/List/Card management) ---
def main_test_application():
    wm = workspace_manager()
    wm.load_workspaces() 

    while True:
        if wm.current_workspace_object:
            ws_name = wm.current_workspace_object.name
            prompt = f"Current Workspace: {ws_name}\n\nChoose an action:"
            choices = [
                "View Current Workspace Details",
                "Manage Current Board", # Changed from "View Board Details"
                "Set/Change Workspace Password",
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

        action = easygui.buttonbox(prompt, title="Workspace Kanban Manager", choices=choices)

        if action is None or action == "Exit":
            if wm.current_workspace_object:
                save_on_exit = easygui.ynbox(f"Do you want to save changes to '{wm.current_workspace_object.name}' before exiting?", "Save on Exit")
                if save_on_exit:
                    wm.save_current_workspace()
            print("Exiting application.")
            break

        if wm.current_workspace_object:
            current_ws = wm.current_workspace_object
            if action == "View Current Workspace Details":
                easygui.msgbox(str(current_ws), title=f"Details for {current_ws.name}")
            
            elif action == "Manage Current Board":
                manage_board_menu(current_ws.get_board(), wm) # Pass workspace manager for saving

            elif action == "Set/Change Workspace Password":
                old_pwd_attempt = None
                if current_ws._pwd:
                    old_pwd_attempt = easygui.passwordbox(f"Enter current password for '{current_ws.name}' to change it:", "Current Password")
                    if old_pwd_attempt is None: 
                        continue 
                
                new_pwd = easygui.passwordbox(f"Enter new password for '{current_ws.name}' (leave blank to remove password):", "New Password")
                if new_pwd is not None: 
                    if current_ws.set_pwd(new_pwd, old_pwd_attempt):
                        # set_pwd shows its own success/error messages
                        # Password change updates last_edited, so save is good.
                        wm.save_current_workspace() 
                    
            elif action == "Save Current Workspace":
                wm.save_current_workspace() # This now updates last_edited automatically
            
            elif action == "Close Current Workspace":
                if current_ws: 
                    save_on_close = easygui.ynbox(f"Do you want to save changes to '{current_ws.name}' before closing?", "Save Changes")
                    if save_on_close:
                        wm.save_current_workspace()
                wm.close_current_workspace()

        if action == "List All Workspaces":
            if wm.available_workspaces:
                msg = "Available Workspaces:\n\n"
                for name, path in wm.available_workspaces.items():
                    msg += f"- {name}: {path}\n"
                easygui.msgbox(msg, title="Available Workspaces")
            else:
                easygui.msgbox("No workspaces configured yet.", title="Available Workspaces")

        elif action == "Create New Workspace": # Typo fixed: Create New Workspacef -> Create New Workspace
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
                        open_now = easygui.ynbox(f"Workspace '{created_ws_obj.name}' created. Open it now?", "Open Workspace")
                        if open_now:
                            wm.current_workspace_object = created_ws_obj 
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
                wm.open_workspace(chosen_ws_name) 

def manage_board_menu(board: Board, wm: workspace_manager):
    """Manages interactions with a Board."""
    while True:
        board_details_str = str(board)
        prompt = f"Managing Board: {board.name}\n\n{board_details_str}\n\nChoose an action for this board:"
        choices = [
            "Create New List",
            "Select List to Manage",
            "Rename Board",
            "Delete List (Select)",
            "Back to Workspace Menu"
        ]
        action = easygui.buttonbox(prompt, f"Board: {board.name}", choices)

        if action is None or action == "Back to Workspace Menu":
            break
        
        if action == "Create New List":
            list_fields = ["Name", "Description (optional)"]
            list_values = easygui.multenterbox("Enter details for the new list:", "Create List", list_fields)
            if list_values:
                list_name, list_desc = list_values
                if list_name:
                    board.create_list(list_name, list_desc or "None")
                    easygui.msgbox(f"List '{list_name}' created. Remember to save the workspace.", "List Created")
                    wm.save_current_workspace() # Optionally save immediately
                else:
                    easygui.msgbox("List name cannot be empty.", "Error")
        
        elif action == "Select List to Manage": #NOTE THIS IS BUGGED AND THERE IS STILL NO EXPLANATION FOR THIS
            if not board.get_all_lists():
                easygui.msgbox("No lists on this board to select.", "Manage List")
                continue
            
            list_choices_dict = {f"{l.list_name} (ID: {l.list_id[:8]})": l.list_id for l in board.get_all_lists()}
            chosen_list_id = safe_choicebox("Select a list to manage:", "Manage List", list_choices_dict)
            
            if chosen_list_id:
                selected_list = board.get_list(chosen_list_id)
                if selected_list:
                    manage_list_menu(selected_list, board, wm)
        
        elif action == "Rename Board":
            new_name = easygui.enterbox(f"Enter new name for board '{board.name}':", "Rename Board", default=board.name)
            if new_name and new_name != board.name:
                board.change_name(new_name)
                easygui.msgbox(f"Board renamed to '{new_name}'. Remember to save.", "Board Renamed")

        elif action == "Delete List (Select)":
            if not board.get_all_lists():
                easygui.msgbox("No lists on this board to delete.", "Delete List")
                continue
            list_choices_dict = {f"{l.list_name} (ID: {l.list_id[:8]})": l.list_id for l in board.get_all_lists()}
            list_id_to_delete = safe_choicebox("Select a list to DELETE:", "Delete List", list_choices_dict)
            if list_id_to_delete:
                list_to_delete = board.get_list(list_id_to_delete)
                if easygui.ynbox(f"Are you sure you want to delete list '{list_to_delete.list_name}' and all its cards?", "Confirm Deletion"):
                    if board.remove_list(list_id_to_delete):
                        easygui.msgbox(f"List '{list_to_delete.list_name}' deleted. Remember to save.", "List Deleted")
                    else:
                        easygui.msgbox(f"Failed to delete list '{list_to_delete.list_name}'.", "Error")


def manage_list_menu(current_list: List, board: Board, wm: workspace_manager):
    """Manages interactions with a List."""
    while True:
        list_details_str = str(current_list)
        prompt = f"Managing List: {current_list.list_name} (on Board: {board.name})\n\n{list_details_str}\n\nChoose an action for this list:"
        choices = [
            "Create New Card",
            "View/Select Card", # To view details or edit/delete
            "Edit List Details",
            "Delete This List",
            "Back to Board Menu"
        ]
        action = easygui.buttonbox(prompt, f"List: {current_list.list_name}", choices)

        if action is None or action == "Back to Board Menu":
            break

        if action == "Create New Card":
            card_fields = ["Name", "Description (optional)"]
            card_values = easygui.multenterbox("Enter details for the new card:", "Create Card", card_fields)
            if card_values:
                card_name, card_desc = card_values
                if card_name:
                    current_list.create_card(card_name, card_desc or "None")
                    easygui.msgbox(f"Card '{card_name}' created in list '{current_list.list_name}'. Remember to save.", "Card Created")
                else:
                    easygui.msgbox("Card name cannot be empty.", "Error")
        
        elif action == "View/Select Card":
            if not current_list.get_all_cards():
                easygui.msgbox("No cards in this list.", "View Cards")
                continue
            
            card_choices_dict = {f"{c.name} (ID: {c.card_id[:8]})": c.card_id for c in current_list.get_all_cards()}
            chosen_card_id = safe_choicebox("Select a card:", "Manage Card", card_choices_dict)

            if chosen_card_id:
                selected_card = current_list.get_card(chosen_card_id)
                if selected_card:
                    # Basic view, could expand to edit/delete card menu
                    easygui.msgbox(str(selected_card), f"Card: {selected_card.name}")
                    # --- Placeholder for managing the selected card ---
                    # card_action = easygui.buttonbox("What to do with this card?", "Card Actions", ["Edit Card", "Delete Card", "Cancel"])
                    # if card_action == "Edit Card": ...
                    # if card_action == "Delete Card": ...

        elif action == "Edit List Details":
            list_fields = ["New Name", "New Description"]
            current_values = [current_list.list_name, current_list.description]
            new_values = easygui.multenterbox(f"Edit details for list '{current_list.list_name}':", "Edit List", list_fields, current_values)
            if new_values:
                new_name, new_desc = new_values
                if new_name:
                    current_list.change_name(new_name)
                    current_list.change_desc(new_desc or "None")
                    easygui.msgbox(f"List details updated. Remember to save.", "List Updated")
                else:
                    easygui.msgbox("List name cannot be empty.", "Error")

        elif action == "Delete This List":
            if easygui.ynbox(f"Are you sure you want to delete list '{current_list.list_name}' and all its cards?", "Confirm Deletion"):
                if board.remove_list(current_list.list_id):
                    easygui.msgbox(f"List '{current_list.list_name}' deleted. Remember to save.", "List Deleted")
                    return # Exit list management as list is gone
                else: # Should not happen if ID was correct
                    easygui.msgbox(f"Error deleting list '{current_list.list_name}'.", "Error")


if __name__ == "__main__":
    main_test_application()