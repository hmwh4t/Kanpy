import os
import json
import datetime
import base64
import shutil
from typing import List, Dict, Optional, Any
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

# --- Configuration ---
DEFAULT_WORKSPACES_DIR = "workspaces"
CONFIG_FILE_NAME = "workspaces.json"
DATA_FILE_NAME = "data.json"
MAX_PASSWORD_ATTEMPTS = 3
SALT_SIZE = 16


class EncryptionHelper:
    """Handles encryption and decryption operations using Fernet."""
    
    @staticmethod
    def derive_key(password, salt):
        """Derive a key from password and salt using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))

    @staticmethod
    def encrypt(data_str, password):
        """Encrypt data string with password."""
        salt = os.urandom(SALT_SIZE)
        key = EncryptionHelper.derive_key(password, salt)
        encrypted = Fernet(key).encrypt(data_str.encode('utf-8'))
        return salt + encrypted

    @staticmethod
    def decrypt(encrypted_data, password):
        """Decrypt data with password."""
        if len(encrypted_data) <= SALT_SIZE:
            raise ValueError("Invalid encrypted data: too short for salt.")
        
        salt = encrypted_data[:SALT_SIZE]
        ciphertext = encrypted_data[SALT_SIZE:]
        key = EncryptionHelper.derive_key(password, salt)
        return Fernet(key).decrypt(ciphertext).decode('utf-8')


class Card:
    """Represents a card with name and description."""
    
    def __init__(self, name, description="No description provided"):
        self.name = name
        self.description = description

    def to_dict(self):
        """Convert card to dictionary."""
        return {"name": self.name, "description": self.description}

    @classmethod
    def from_dict(cls, data):
        """Create card from dictionary."""
        return cls(
            name=data.get("name", "Untitled Card"),
            description=data.get("description", "No description provided")
        )

    def update_name(self, new_name):
        """Update card name."""
        old_name = self.name
        self.name = new_name
        print(f"Card name changed from '{old_name}' to '{new_name}'")

    def update_description(self, new_description):
        """Update card description."""
        self.description = new_description
        print(f"Card '{self.name}' description updated")


class ListObject:
    """A container for managing lists and their cards."""
    
    def __init__(self, name="Untitled List", description="No description provided", cards=None):
        self.name = name
        self.description = description
        self._cards = []
        
        if cards:
            self._cards = [Card.from_dict(card) if isinstance(card, dict) else card 
                          for card in cards]

    @property
    def cards(self):
        """Return cards as dictionaries for compatibility."""
        return [card.to_dict() if hasattr(card, 'to_dict') else card 
                for card in self._cards]

    def change_name(self, new_name):
        """Change the name of the list."""
        old_name = self.name
        self.name = new_name
        print(f"List name changed from '{old_name}' to '{new_name}'")

    def update_description(self, new_description):
        """Update list description."""
        self.description = new_description
        print(f"List '{self.name}' description updated")

    def create_card(self, card_name, card_description="No description provided"):
        """Create a new card in this list."""
        new_card = Card(card_name, card_description)
        self._cards.append(new_card)
        print(f"Added card '{card_name}' to list '{self.name}'")
        return new_card

    def remove_card(self, card_name):
        """Remove a card by name."""
        for i, card in enumerate(self._cards):
            if card.name == card_name:
                removed_card = self._cards.pop(i)
                print(f"Removed card '{removed_card.name}' from list '{self.name}'")
                return True
        print(f"Card '{card_name}' not found in list '{self.name}'")
        return False

    def get_card_count(self):
        """Get the number of cards in this list."""
        return len(self._cards)

    def to_dict(self):
        """Convert list to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "cards": self.cards
        }

    @classmethod
    def from_dict(cls, data):
        """Create list from dictionary."""
        return cls(
            name=data.get("name", "Untitled List"),
            description=data.get("description", "No description provided"),
            cards=data.get("cards", [])
        )


class Board:
    """A container for managing board state and lists."""
    
    def __init__(self, name="Default Board", lists=None):
        self.name = name
        self._list_objects = []
        
        if lists:
            self._list_objects = [ListObject.from_dict(list_data) for list_data in lists]

    @property
    def list_objects(self):
        """Get list objects."""
        return self._list_objects

    @property
    def lists(self):
        """Return lists as dictionaries for compatibility."""
        return [list_obj.to_dict() for list_obj in self._list_objects]

    def create_list(self, name, description="No description provided"):
        """Create a new list in the board."""
        new_list = ListObject(name=name, description=description)
        self._list_objects.append(new_list)
        print(f"Added list '{name}' to board '{self.name}'. Don't forget to save.")
        return new_list

    def remove_list(self, list_name):
        """Remove a list by name."""
        for i, list_obj in enumerate(self._list_objects):
            if list_obj.name == list_name:
                removed_list = self._list_objects.pop(i)
                print(f"Removed list '{removed_list.name}' from board '{self.name}'")
                return True
        print(f"List '{list_name}' not found in board '{self.name}'")
        return False

    def get_list_by_name(self, list_name):
        """Get a list by name."""
        for list_obj in self._list_objects:
            if list_obj.name == list_name:
                return list_obj
        return None

    def get_list_count(self):
        """Get the number of lists in this board."""
        return len(self._list_objects)

    def to_dict(self):
        """Convert board to dictionary."""
        return {"name": self.name, "lists": self.lists}

    @classmethod
    def from_dict(cls, data):
        """Create board from dictionary."""
        return cls(name=data.get("name", "Default Board"), lists=data.get("lists", []))


class Workspace:
    """Represents a workspace containing boards and metadata."""
    
    def __init__(self, name, password=None, path=None):
        self.name = name
        self.path = path
        self._password = password
        self.last_edited = datetime.datetime.now(datetime.timezone.utc)
        self._boards = [Board(name=f"{name} Board")]
        self._selected_board_index = 0

    @property
    def boards(self):
        """Get all boards in the workspace."""
        return self._boards

    @property
    def board(self):
        """Get the primary board (for backward compatibility)."""
        if not self._boards:
            self._boards.append(Board(name=f"{self.name} Board"))
            self._selected_board_index = 0
        return self._boards[0]

    @property
    def selected_board(self):
        """Get the currently selected board."""
        if 0 <= self._selected_board_index < len(self._boards):
            return self._boards[self._selected_board_index]
        return self.board if self._boards else None

    def create_board(self, name):
        """Create a new board in the workspace."""
        new_board = Board(name=name)
        self._boards.append(new_board)
        print(f"Created board '{name}' in workspace '{self.name}'")
        return new_board

    def select_board(self, board_name):
        """Select a board by name."""
        for i, board in enumerate(self._boards):
            if board.name.lower() == board_name.lower():
                self._selected_board_index = i
                print(f"Selected board '{board.name}'")
                return True
        print(f"Board '{board_name}' not found")
        return False

    def remove_board(self, board_name):
        """Remove a board by name."""
        if len(self._boards) <= 1:
            print("Cannot remove the last board")
            return False
            
        for i, board in enumerate(self._boards):
            if board.name == board_name:
                removed_board = self._boards.pop(i)
                if self._selected_board_index >= len(self._boards):
                    self._selected_board_index = len(self._boards) - 1
                print(f"Removed board '{removed_board.name}' from workspace '{self.name}'")
                return True
        print(f"Board '{board_name}' not found")
        return False

    def set_password(self, new_password):
        """Set or clear the workspace password."""
        self._password = new_password.strip() if new_password else None
        status = "set" if self._password else "cleared"
        print(f"Password has been {status} for this session. Save the workspace to apply permanently.")

    def has_password(self):
        """Check if workspace has a password."""
        return self._password is not None

    def update_last_edited(self):
        """Update the last edited timestamp."""
        self.last_edited = datetime.datetime.now(datetime.timezone.utc)

    def to_dict(self):
        """Convert workspace to dictionary."""
        return {
            "name": self.name,
            "last_edited": self.last_edited.isoformat(),
            "boards": [board.to_dict() for board in self._boards],
            "selected_board_index": self._selected_board_index
        }

    @classmethod
    def from_dict(cls, data, path):
        """Create workspace from dictionary."""
        workspace = cls(name=data.get("name", "Unnamed"), path=path)
        
        # Handle last_edited
        if last_edited_str := data.get("last_edited"):
            try:
                workspace.last_edited = datetime.datetime.fromisoformat(last_edited_str)
            except ValueError:
                workspace.last_edited = datetime.datetime.now(datetime.timezone.utc)
        
        # Handle boards
        if boards_data := data.get("boards"):
            workspace._boards = [Board.from_dict(b_data) for b_data in boards_data]
        elif board_data := data.get("board"):  # Backward compatibility
            workspace._boards = [Board.from_dict(board_data)]
        
        # Handle selected board index
        workspace._selected_board_index = data.get("selected_board_index", 0)
        if workspace._selected_board_index >= len(workspace._boards):
            workspace._selected_board_index = 0
            
        return workspace


class WorkspaceManager:
    """Main controller for workspace operations."""
    
    def __init__(self, config_path=CONFIG_FILE_NAME, workspaces_dir=DEFAULT_WORKSPACES_DIR):
        self.workspaces_dir = workspaces_dir
        self.config_path = config_path
        self._workspaces_registry = {}
        self._current_workspace = None
        
        self._initialize()

    @property
    def current_workspace(self):
        """Get the currently open workspace."""
        return self._current_workspace

    def _initialize(self):
        """Initialize the workspace manager."""
        os.makedirs(self.workspaces_dir, exist_ok=True)
        self._load_master_config()

    def _load_master_config(self):
        """Load the master configuration file."""
        if not os.path.exists(self.config_path):
            self._workspaces_registry = {}
            return
            
        try:
            with open(self.config_path, "r") as f:
                self._workspaces_registry = json.load(f)
            self._clean_invalid_workspaces()
        except (IOError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load config file: {e}. Starting fresh.")
            self._workspaces_registry = {}

    def _save_master_config(self):
        """Save the master configuration file."""
        try:
            with open(self.config_path, "w") as f:
                json.dump(self._workspaces_registry, f, indent=2)
        except IOError as e:
            print(f"Error: Could not save master config: {e}")

    def _clean_invalid_workspaces(self):
        """Remove invalid workspace entries from registry."""
        initial_count = len(self._workspaces_registry)
        self._workspaces_registry = {
            name: path for name, path in self._workspaces_registry.items()
            if os.path.isdir(path) and os.path.exists(os.path.join(path, DATA_FILE_NAME))
        }
        if len(self._workspaces_registry) != initial_count:
            self._save_master_config()

    def _is_file_encrypted(self, file_path):
        """Check if a file is encrypted."""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                try:
                    content.decode('utf-8')
                    json.loads(content.decode('utf-8'))
                    return False
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return True
        except IOError:
            return False

    def _prompt_password(self, prompt_text):
        """Prompt user for password with retry logic."""
        for attempt in range(MAX_PASSWORD_ATTEMPTS):
            prompt = f"{prompt_text} (attempt {attempt + 1}/{MAX_PASSWORD_ATTEMPTS}, type 'CANCEL' to abort): "
            password = input(prompt).strip()
            if password.upper() == "CANCEL":
                return None
            if password:
                return password
            print("Password cannot be empty.")
        print("Maximum password attempts reached.")
        return None

    def create_workspace(self, name):
        """Create a new workspace."""
        if not name or name in self._workspaces_registry:
            print(f"Error: Invalid or duplicate workspace name '{name}'.")
            return None
        
        path = os.path.join(self.workspaces_dir, name)
        if os.path.exists(path):
            print(f"Error: Directory '{path}' already exists.")
            return None

        try:
            os.makedirs(path)
            workspace = Workspace(name, path=path)
            self._current_workspace = workspace
            self.save_current_workspace()
            
            self._workspaces_registry[name] = path
            self._save_master_config()
            print(f"Successfully created and opened workspace: {name}")
            return workspace
        except OSError as e:
            print(f"Error creating workspace: {e}")
            return None

    def open_workspace(self, name):
        """Open an existing workspace."""
        if self._current_workspace:
            print(f"Please close the current workspace ('{self._current_workspace.name}') first.")
            return None
            
        if name not in self._workspaces_registry:
            print(f"Error: Workspace '{name}' not found.")
            return None
        
        path = self._workspaces_registry[name]
        data_path = os.path.join(path, DATA_FILE_NAME)
        
        try:
            is_encrypted = self._is_file_encrypted(data_path)
            password = None
            
            if is_encrypted:
                password = self._prompt_password(f"Enter password for '{name}'")
                if not password:
                    return None

            with open(data_path, "rb") as f:
                file_content = f.read()
            
            if password:
                data_str = EncryptionHelper.decrypt(file_content, password)
            else:
                data_str = file_content.decode('utf-8')
                
            workspace_data = json.loads(data_str)
            workspace = Workspace.from_dict(workspace_data, path)
            workspace._password = password
            self._current_workspace = workspace
            print(f"Successfully opened workspace: {name}")
            return workspace

        except InvalidToken:
            print("Error: Incorrect password or corrupted data file.")
        except (IOError, json.JSONDecodeError, ValueError) as e:
            print(f"Error opening workspace '{name}': {e}")
        return None

    def save_current_workspace(self):
        """Save the currently open workspace."""
        if not self._current_workspace:
            print("No active workspace to save.")
            return False

        workspace = self._current_workspace
        workspace.update_last_edited()
        data_path = os.path.join(workspace.path, DATA_FILE_NAME)
        json_data = json.dumps(workspace.to_dict(), indent=2)

        try:
            if workspace.has_password():
                encrypted_data = EncryptionHelper.encrypt(json_data, workspace._password)
                with open(data_path, "wb") as f:
                    f.write(encrypted_data)
            else:
                with open(data_path, "w", encoding='utf-8') as f:
                    f.write(json_data)
            print(f"Workspace '{workspace.name}' saved successfully.")
            return True
        except IOError as e:
            print(f"Error saving workspace: {e}")
            return False
    
    def close_current_workspace(self):
        """Close the currently open workspace."""
        if not self._current_workspace:
            print("No workspace is currently open.")
            return
            
        name = self._current_workspace.name
        self._current_workspace = None
        print(f"Workspace '{name}' has been closed.")

    def list_workspaces(self):
        """Get a list of all available workspaces."""
        return list(self._workspaces_registry.keys())

    def delete_workspace(self, name):
        """Delete a workspace permanently."""
        if name not in self._workspaces_registry:
            print(f"Error: Workspace '{name}' not found.")
            return False
            
        if self._current_workspace and self._current_workspace.name == name:
            print("Cannot delete the currently open workspace. Close it first.")
            return False
            
        path = self._workspaces_registry[name]
        try:
            shutil.rmtree(path)
            del self._workspaces_registry[name]
            self._save_master_config()
            print(f"Workspace '{name}' deleted successfully.")
            return True
        except OSError as e:
            print(f"Error deleting workspace '{name}': {e}")
            return False

    @property
    def workspaces(self):
        """Get the workspaces registry (for backward compatibility)."""
        return self._workspaces_registry


# --- CLI Test Function ---
def clear_console():
    """Clear the console screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def test_cli():
    """Run an interactive command-line interface to test the WorkspaceManager."""
    manager = WorkspaceManager()
    clear_console()
    
    while True:
        print("="*50)
        status = f"Current Workspace: {manager.current_workspace.name if manager.current_workspace else 'None'}"
        print(f"MENU\t\t{status}")
        print("-"*50)
        print("  list            - List all workspaces")
        print("  create <name>   - Create a new workspace")
        print("  open <name>     - Open a workspace")
        print("  close           - Close the current workspace")
        print("  save            - Save the current workspace")
        print("  view            - View the current workspace's board")
        print("  boards          - List all boards in current workspace")
        print("  createboard <name> - Create a new board")
        print("  selectboard <name> - Select a board to work with")
        print("  lists           - List all lists in selected board")
        print("  addlist <name>  - Add a list to the selected board")
        print("  password <pass> - Set/change password for the open workspace")
        print("  clear           - Clear the console screen")
        print("  cleanup         - DELETE all workspaces and config")
        print("  quit            - Exit the program")
        print("="*50)
        
        # Show selected board if workspace is open
        if manager.current_workspace:
            selected_board = manager.current_workspace.selected_board
            if selected_board:
                print(f"Selected Board: {selected_board.name}")
            print("-"*50)
        
        command_line = input("> ").strip().lower().split(maxsplit=1)
        if not command_line:
            continue
            
        cmd = command_line[0]
        args = command_line[1] if len(command_line) > 1 else ""

        # --- Command Processing ---
        if cmd == 'quit':
            break
        elif cmd == 'list':
            workspaces = manager.list_workspaces()
            if not workspaces:
                print("\nNo workspaces found.")
            else:
                print("\nAvailable workspaces:")
                for ws in workspaces:
                    print(f"- {ws}")
        elif cmd == 'create':
            if not args: 
                print("Usage: create <workspace_name>")
            else: 
                manager.create_workspace(args)
        elif cmd == 'open':
            if not args: 
                print("Usage: open <workspace_name>")
            else: 
                manager.open_workspace(args)
        elif cmd == 'close':
            manager.close_current_workspace()
        elif cmd == 'save':
            manager.save_current_workspace()
        elif cmd == 'view':
            if manager.current_workspace and manager.current_workspace.boards:
                selected_board = manager.current_workspace.selected_board
                print(json.dumps(selected_board.to_dict(), indent=2))
            else:
                print("\nNo workspace is open or it has no boards.")
        elif cmd == 'boards':
            if not manager.current_workspace:
                print("\nNo workspace is open.")
            elif not manager.current_workspace.boards:
                print("\nNo boards in current workspace.")
            else:
                print("\nBoards in current workspace:")
                selected_board = manager.current_workspace.selected_board
                for i, board in enumerate(manager.current_workspace.boards):
                    marker = " (selected)" if board == selected_board else ""
                    print(f"{i+1}. {board.name}{marker}")
        elif cmd == 'createboard':
            if not manager.current_workspace:
                print("\nNo workspace is open.")
            elif not args:
                print("Usage: createboard <board_name>")
            else:
                new_board = manager.current_workspace.create_board(args)
                manager.current_workspace.select_board(args)
                print("Don't forget to save.")
        elif cmd == 'selectboard':
            if not manager.current_workspace:
                print("\nNo workspace is open.")
            elif not args:
                print("Usage: selectboard <board_name>")
            else:
                manager.current_workspace.select_board(args)
        elif cmd == 'lists':
            if not manager.current_workspace:
                print("\nNo workspace is open.")
            else:
                selected_board = manager.current_workspace.selected_board
                if not selected_board:
                    print("\nNo board selected.")
                elif not selected_board.list_objects:
                    print(f"\nNo lists in board '{selected_board.name}'.")
                else:
                    print(f"\nLists in board '{selected_board.name}':")
                    for i, list_obj in enumerate(selected_board.list_objects):
                        print(f"{i+1}. {list_obj.name} - {list_obj.description}")
                        print(f"   Cards: {list_obj.get_card_count()}")
        elif cmd == 'addlist':
            if not manager.current_workspace:
                print("\nNo workspace is open.")
            elif not args:
                print("Usage: addlist <list_name>")
            else:
                selected_board = manager.current_workspace.selected_board
                if not selected_board:
                    print("\nNo board selected.")
                else:
                    selected_board.create_list(args)
        elif cmd == 'password':
            if not manager.current_workspace:
                print("\nNo workspace is open.")
            else:
                manager.current_workspace.set_password(args)
        elif cmd == 'clear':
            clear_console()
            continue
        elif cmd == 'cleanup':
            confirm = input("This will DELETE ALL workspaces and data. Are you sure? (y/n): ").lower()
            if confirm == 'y':
                manager.close_current_workspace()
                try:
                    shutil.rmtree(manager.workspaces_dir)
                    print(f"Removed directory: {manager.workspaces_dir}")
                except FileNotFoundError: 
                    pass
                try:
                    os.remove(manager.config_path)
                    print(f"Removed config file: {manager.config_path}")
                except FileNotFoundError: 
                    pass
                
                print("\nCleanup successful.")
                manager = WorkspaceManager()
        else:
            print("\nUnknown command.")

        # --- Wait for user and clear screen ---
        input("\nPress Enter to continue...")
        clear_console()


if __name__ == "__main__":
    test_cli()
