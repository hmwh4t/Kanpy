import os
import json
import datetime
import base64
import shutil
import random
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

# --- Configuration Constants ---
DEFAULT_WORKSPACES_DIR = "workspaces"
CONFIG_FILE_NAME = "workspaces.json"
DATA_FILE_NAME = "data.json"
MAX_PASSWORD_ATTEMPTS = 3
SALT_SIZE = 16


class EncryptionHelper:
    """Handles encryption and decryption operations using Fernet."""
    def derive_key(password, salt):
        """Derive a key from password and salt using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        derived_key = kdf.derive(password.encode('utf-8'))
        return base64.urlsafe_b64encode(derived_key)

    def encrypt(data_str, password):
        """Encrypt data string with password."""
        salt = os.urandom(SALT_SIZE)
        key = EncryptionHelper.derive_key(password, salt)
        fernet = Fernet(key)
        encrypted = fernet.encrypt(data_str.encode('utf-8'))
        return salt + encrypted

    def decrypt(encrypted_data, password):
        """Decrypt data with password."""
        if len(encrypted_data) <= SALT_SIZE:
            raise ValueError("Invalid encrypted data: too short for salt.")
        
        salt = encrypted_data[:SALT_SIZE]
        ciphertext = encrypted_data[SALT_SIZE:]
        key = EncryptionHelper.derive_key(password, salt)
        fernet = Fernet(key)
        return fernet.decrypt(ciphertext).decode('utf-8')


class Card:
    """Represents a card with name, description, deadline, and priority."""
    
    def __init__(self, name, description="No description provided", deadline=None, priority=0):
        self.name = name
        self.description = description
        self.deadline = deadline
        self.priority = priority

    def to_dict(self):
        """Convert card to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "deadline": self.deadline,
            "priority": self.priority
        }

    def from_dict(cls, data):
        """Create card from dictionary."""
        return cls(
            name=data.get("name", "Untitled Card"),
            description=data.get("description", "No description provided"),
            deadline=data.get("deadline", None),
            priority=data.get("priority", 0)
        )

    def update_name(self, new_name):
        """Update card name."""
        old_name = self.name
        self.name = new_name
        self.deadline = -1  # Reset deadline when name changes
        print(f"Card name changed from '{old_name}' to '{new_name}'")

    def update_description(self, new_description):
        """Update card description."""
        self.description = new_description
        print(f"Card '{self.name}' description updated")

    def update_deadline(self, new_deadline):
        """Update card deadline."""
        self.deadline = new_deadline
        print(f"Card '{self.name}' deadline updated")

    def update_priority(self, new_priority):
        """Update card priority."""
        self.priority = new_priority
        print(f"Card '{self.name}' priority updated")


class ListObject:
    """A container for managing lists and their cards."""
    def __init__(self, name="Untitled List", description="No description provided", cards=None):
        self.name = name
        self.description = description
        self._cards = []
        
        if cards:
            self._cards = [
                Card.from_dict(card) if isinstance(card, dict) else card 
                for card in cards
            ]

    def cards(self):
        """Return cards as dictionaries for compatibility."""
        return [
            card.to_dict() if hasattr(card, 'to_dict') else card 
            for card in self._cards
        ]

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

    def get_card_count(self):
        """Get the number of cards in this list."""
        return len(self._cards)

    def to_dict(self):
        """Convert list to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "cards": self.cards()
        }
    
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
            self._list_objects = [
                ListObject.from_dict(list_data) for list_data in lists
            ]

    def list_objects(self):
        """Get list objects."""
        return self._list_objects

    def lists(self):
        """Return lists as dictionaries for compatibility."""
        return [list_obj.to_dict() for list_obj in self._list_objects]

    def create_list(self, name, description="No description provided"):
        """Create a new list in the board."""
        new_list = ListObject(name=name, description=description)
        self._list_objects.append(new_list)
        print(f"Added list '{name}' to board '{self.name}'. Don't forget to save.")
        return new_list

    def get_list_by_name(self, list_name):
        """Get a list by name."""
        for list_obj in self._list_objects:
            if list_obj.name == list_name:
                return list_obj
        return None

    def to_dict(self):
        """Convert board to dictionary for serialization."""
        return {
            "name": self.name,
            "lists": self.lists()
        }
    
    def from_dict(cls, data):
        """Create board from dictionary."""
        return cls(
            name=data.get("name", "Default Board"), 
            lists=data.get("lists", [])
        )


class Workspace:
    """Represents a workspace containing boards and metadata."""
    def __init__(self, name, password=None, path=None):
        self.name = name
        self.path = path
        self._password = password
        self.last_edited = datetime.datetime.now().astimezone() 
        self._boards = [Board(name=f"{name} Board")]
        self._selected_board_index = 0

    def boards(self):
        """Get all boards in the workspace."""
        return self._boards

    def board(self):
        """Get the primary board (for backward compatibility)."""
        if not self._boards:
            self._boards.append(Board(name=f"{self.name} Board"))
            self._selected_board_index = 0
        return self._boards[0]

    def selected_board(self):
        """Get the currently selected board."""
        if 0 <= self._selected_board_index < len(self._boards):
            return self._boards[self._selected_board_index]
        return self.board() if self._boards else None

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
        self.last_edited = datetime.datetime.now().astimezone() 

    def to_dict(self):
        """Convert workspace to dictionary for serialization."""
        return {
            "name": self.name,
            "last_edited": self.last_edited.isoformat(),
            "boards": [board.to_dict() for board in self._boards],
            "selected_board_index": self._selected_board_index
        }

    def from_dict(cls, data, path):
        """Create workspace from dictionary."""
        workspace = cls(name=data.get("name", "Unnamed"), path=path)
        
        # Handle last_edited timestamp
        last_edited_str = data.get("last_edited")
        if last_edited_str:
            try:
                workspace.last_edited = datetime.datetime.fromisoformat(last_edited_str)
            except ValueError:
                workspace.last_edited = datetime.datetime.now(datetime.timezone.utc)
        
        # Handle boards data
        boards_data = data.get("boards")
        if boards_data:
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
        """Check if a file is encrypted by attempting to decode it as JSON."""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                try:
                    decoded_content = content.decode('utf-8')
                    json.loads(decoded_content)
                    return False  # Successfully decoded as JSON
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return True  # Failed to decode, likely encrypted
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
            
            # Decrypt or decode the content
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

    def workspaces(self):
        """Get the workspaces registry (for backward compatibility)."""
        return self._workspaces_registry


# --- Utility Functions ---
def clear_console():
    """Clear the console screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def test_cli():
    """Creates a test environment with pre-populated data."""
    manager = WorkspaceManager()
    print("--- Cleaning up previous environment ---")
    
    # Clean up existing workspaces and config to ensure a fresh start
    try:
        if os.path.exists(manager.workspaces_dir):
            shutil.rmtree(manager.workspaces_dir)
        if os.path.exists(manager.config_path):
            os.remove(manager.config_path)
        print("Cleanup successful.")
    except OSError as e:
        print(f"Error during cleanup: {e}")

    # Re-initialize manager after cleanup
    manager = WorkspaceManager()
    print("\n--- Setting up new test environment ---")

    # Create test workspaces
    for workspace_num in range(1, 3):
        ws_name = f"TestWorkspace{workspace_num}"
        print(f"\nCreating workspace: {ws_name}")
        workspace = manager.create_workspace(ws_name)
        
        if not workspace:
            print(f"Failed to create {ws_name}")
            continue

        # Create boards for each workspace
        for board_num in range(1, 6):
            board_name = f"Board {workspace_num}-{board_num}"
            board = workspace.create_board(board_name)

            # Create lists for each board
            num_lists = random.randint(2, 5)
            for list_num in range(1, num_lists + 1):
                list_name = f"List {workspace_num}-{board_num}-{list_num}"
                list_obj = board.create_list(
                    list_name, 
                    f"Description for {list_name}"
                )

                # Create cards for each list
                num_cards = random.randint(1, 8)
                for card_num in range(1, num_cards + 1):
                    card_name = f"Card {workspace_num}-{board_num}-{list_num}-{card_num}"
                    card = list_obj.create_card(
                        card_name, 
                        f"Description for {card_name}"
                    )

                    # Set random priority
                    card.update_priority(random.randint(0, 5))

                    # Set a random deadline for about 50% of cards
                    if random.random() > 0.5:
                        days_ahead = random.randint(1, 30)
                        deadline_date = datetime.datetime.now() + datetime.timedelta(days=days_ahead)
                        card.update_deadline(deadline_date.isoformat())

        print(f"Saving workspace: {ws_name}")
        manager.save_current_workspace()
        manager.close_current_workspace()

    print("\n--- Test environment setup complete! ---")
    print("Available workspaces:")
    for workspace in manager.list_workspaces():
        print(f"- {workspace}")
    print("\nYou can now run the interactive CLI to explore the generated data.")


if __name__ == "__main__":
    test_cli()
