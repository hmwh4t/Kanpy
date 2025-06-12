import os
import json
import datetime
from typing import Optional, Dict, List as ListType
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64

# Configuration
DEFAULT_WORKSPACES_DIR = "workspaces"
CONFIG_FILE_NAME = "workspaces.json"
WORKSPACE_DATA_FILE_NAME = "workspace.data"
MAX_PASSWORD_ATTEMPTS = 3
SALT_SIZE = 16
KDF_ITERATIONS = 100_000

class EncryptionHelper:
    """Handles encryption and decryption operations."""
    
    @staticmethod
    def derive_key(password: str, salt: bytes) -> bytes:
        """Derive encryption key from password and salt."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=KDF_ITERATIONS,
            backend=default_backend()
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))
    
    @staticmethod
    def encrypt(data: str, password: str) -> bytes:
        """Encrypt data with password."""
        salt = os.urandom(SALT_SIZE)
        key = EncryptionHelper.derive_key(password, salt)
        encrypted = Fernet(key).encrypt(data.encode('utf-8'))
        return salt + encrypted
    
    @staticmethod
    def decrypt(encrypted_data: bytes, password: str) -> str:
        """Decrypt data with password."""
        if len(encrypted_data) <= SALT_SIZE:
            raise ValueError("Invalid encrypted data")
        
        salt = encrypted_data[:SALT_SIZE]
        ciphertext = encrypted_data[SALT_SIZE:]
        key = EncryptionHelper.derive_key(password, salt)
        
        return Fernet(key).decrypt(ciphertext).decode('utf-8')

class Card:
    """Represents a card in a list."""
    
    def __init__(self, name: str, description: str = "No description"):
        self.name = name
        self.description = description
    
    def update_description(self, new_description: str):
        """Update card description."""
        self.description = new_description if new_description else "No description"
    
    def to_dict(self) -> Dict:
        """Convert card to dictionary."""
        return {
            "name": self.name,
            "description": self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Card':
        """Create card from dictionary."""
        return cls(
            name=data.get("name", "Unnamed Card"),
            description=data.get("description", "No description")
        )

class TaskList:
    """Represents a list containing cards."""
    
    def __init__(self, name: str, description: str = "No description"):
        self.name = name
        self.description = description
        self.cards: ListType[Card] = []
    
    def add_card(self, name: str, description: str = "No description") -> Card:
        """Add a new card to the list."""
        if not name:
            raise ValueError("Card name cannot be empty")
        
        # Check for duplicate names
        if any(card.name == name for card in self.cards):
            raise ValueError(f"Card '{name}' already exists")
        
        card = Card(name, description)
        self.cards.append(card)
        return card
    
    def remove_card(self, card_name: str) -> bool:
        """Remove a card by name."""
        for i, card in enumerate(self.cards):
            if card.name == card_name:
                self.cards.pop(i)
                return True
        return False
    
    def get_card(self, card_name: str) -> Optional[Card]:
        """Get a card by name."""
        for card in self.cards:
            if card.name == card_name:
                return card
        return None
    
    def update_name(self, new_name: str):
        """Update list name."""
        if not new_name:
            raise ValueError("List name cannot be empty")
        self.name = new_name
    
    def update_description(self, new_description: str):
        """Update list description."""
        self.description = new_description if new_description else "No description"
    
    def to_dict(self) -> Dict:
        """Convert list to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "cards": [card.to_dict() for card in self.cards]
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TaskList':
        """Create list from dictionary."""
        task_list = cls(
            name=data.get("name", "Unnamed List"),
            description=data.get("description", "No description")
        )
        
        # Load cards
        for card_data in data.get("cards", []):
            card = Card.from_dict(card_data)
            task_list.cards.append(card)
        
        return task_list

class Board:
    """Represents a board containing lists."""
    
    def __init__(self, name: str = "Default Board"):
        self.name = name
        self.lists: ListType[TaskList] = []
    
    def add_list(self, name: str, description: str = "No description") -> TaskList:
        """Add a new list to the board."""
        if not name:
            raise ValueError("List name cannot be empty")
        
        # Check for duplicate names
        if any(task_list.name == name for task_list in self.lists):
            raise ValueError(f"List '{name}' already exists")
        
        task_list = TaskList(name, description)
        self.lists.append(task_list)
        return task_list
    
    def remove_list(self, list_name: str) -> bool:
        """Remove a list by name."""
        for i, task_list in enumerate(self.lists):
            if task_list.name == list_name:
                self.lists.pop(i)
                return True
        return False
    
    def get_list(self, list_name: str) -> Optional[TaskList]:
        """Get a list by name."""
        for task_list in self.lists:
            if task_list.name == list_name:
                return task_list
        return None
    
    def update_name(self, new_name: str):
        """Update board name."""
        if not new_name:
            raise ValueError("Board name cannot be empty")
        self.name = new_name
    
    def to_dict(self) -> Dict:
        """Convert board to dictionary."""
        return {
            "name": self.name,
            "lists": [task_list.to_dict() for task_list in self.lists]
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Board':
        """Create board from dictionary."""
        board = cls(name=data.get("name", "Default Board"))
        
        # Load lists
        for list_data in data.get("lists", []):
            task_list = TaskList.from_dict(list_data)
            board.lists.append(task_list)
        
        return board

class Workspace:
    """Represents a workspace with optional password protection."""
    
    def __init__(self, name: str, password: Optional[str] = None):
        self.name = name
        self._password = password
        self.last_edited = datetime.datetime.now(datetime.timezone.utc)
        self.board = Board(f"{name}'s Board")
    
    def check_password(self, password: Optional[str]) -> bool:
        """Check if password is correct."""
        if not self._password:
            return not password
        return self._password == password
    
    def set_password(self, new_password: Optional[str], old_password: Optional[str] = None) -> bool:
        """Set or change workspace password."""
        if self._password and self._password != old_password:
            return False
        
        self._password = new_password.strip() if new_password else None
        self.last_edited = datetime.datetime.now(datetime.timezone.utc)
        return True
    
    def to_dict(self) -> Dict:
        """Convert workspace to dictionary."""
        return {
            "name": self.name,
            "password": self._password,
            "last_edited": self.last_edited.isoformat(),
            "board": self.board.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Workspace':
        """Create workspace from dictionary."""
        workspace = cls(data.get("name", "Unnamed"))
        workspace._password = data.get("password")
        
        # Handle last_edited
        if data.get("last_edited"):
            try:
                workspace.last_edited = datetime.datetime.fromisoformat(data["last_edited"])
            except ValueError:
                pass  # Keep default time
        
        # Handle board
        if data.get("board"):
            workspace.board = Board.from_dict(data["board"])
        
        return workspace

class FileManager:
    """Handles file operations for workspaces."""
    
    @staticmethod
    def load_json(file_path: str) -> Dict:
        """Load JSON data from file."""
        with open(file_path, "r") as f:
            return json.load(f)
    
    @staticmethod
    def save_json(data: Dict, file_path: str):
        """Save JSON data to file."""
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)
    
    @staticmethod
    def load_encrypted(file_path: str, password: str) -> Dict:
        """Load encrypted data from file."""
        with open(file_path, "rb") as f:
            encrypted_data = f.read()
        
        decrypted_json = EncryptionHelper.decrypt(encrypted_data, password)
        return json.loads(decrypted_json)
    
    @staticmethod
    def save_encrypted(data: Dict, file_path: str, password: str):
        """Save encrypted data to file."""
        json_data = json.dumps(data, indent=2)
        encrypted_data = EncryptionHelper.encrypt(json_data, password)
        
        with open(file_path, "wb") as f:
            f.write(encrypted_data)

class WorkspaceManager:
    """Manages multiple workspaces."""
    
    def __init__(self, workspaces_dir: str = DEFAULT_WORKSPACES_DIR):
        self.workspaces_dir = workspaces_dir
        self.config_file = CONFIG_FILE_NAME
        self.workspaces: Dict[str, str] = {}  # name -> path mapping
        self.current_workspace: Optional[Workspace] = None
        
        # Ensure workspaces directory exists
        os.makedirs(self.workspaces_dir, exist_ok=True)
    
    def load_config(self):
        """Load workspace configuration from file."""
        if not os.path.exists(self.config_file):
            self.workspaces = {}
            self.save_config()
            return
        
        try:
            self.workspaces = FileManager.load_json(self.config_file)
            self._clean_invalid_workspaces()
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading config: {e}. Starting fresh.")
            self.workspaces = {}
            self.save_config()
    
    def save_config(self):
        """Save workspace configuration to file."""
        try:
            FileManager.save_json(self.workspaces, self.config_file)
        except IOError as e:
            print(f"Error saving config: {e}")
    
    def _clean_invalid_workspaces(self):
        """Remove invalid workspace entries from config."""
        valid_workspaces = {}
        for name, path in self.workspaces.items():
            data_file = os.path.join(path, WORKSPACE_DATA_FILE_NAME)
            if os.path.isdir(path) and os.path.exists(data_file):
                valid_workspaces[name] = path
            else:
                print(f"Removing invalid workspace: {name}")
        
        if len(valid_workspaces) != len(self.workspaces):
            self.workspaces = valid_workspaces
            self.save_config()
    
    def create_workspace(self, name: str) -> Optional[Workspace]:
        """Create a new workspace."""
        if not name or name in self.workspaces:
            print(f"Invalid or duplicate workspace name: {name}")
            return None
        
        workspace_path = os.path.join(self.workspaces_dir, name)
        if os.path.exists(workspace_path):
            print(f"Directory already exists: {workspace_path}")
            return None
        
        try:
            os.makedirs(workspace_path, exist_ok=True)
            
            # Create workspace and save it
            workspace = Workspace(name)
            data_file = os.path.join(workspace_path, WORKSPACE_DATA_FILE_NAME)
            
            FileManager.save_json(workspace.to_dict(), data_file)
            
            self.workspaces[name] = workspace_path
            self.save_config()
            
            print(f"Created workspace: {name}")
            return workspace
            
        except OSError as e:
            print(f"Error creating workspace: {e}")
            return None
    
    def _is_encrypted_file(self, file_path: str) -> bool:
        """Check if file contains encrypted data."""
        try:
            FileManager.load_json(file_path)
            return False
        except (json.JSONDecodeError, UnicodeDecodeError):
            return True
    
    def _prompt_password(self, prompt_text: str) -> Optional[str]:
        """Prompt for password with retry logic."""
        for attempt in range(MAX_PASSWORD_ATTEMPTS):
            password = input(f"{prompt_text} (attempt {attempt + 1}/{MAX_PASSWORD_ATTEMPTS}, 'CANCEL' to abort): ").strip()
            
            if password == "CANCEL":
                return None
            
            if password:
                return password
            
            print("Password cannot be empty")
        
        print("Maximum attempts reached")
        return None
    
    def open_workspace(self, name: str) -> Optional[Workspace]:
        """Open a workspace by name."""
        if name not in self.workspaces:
            print(f"Workspace not found: {name}")
            return None
        
        workspace_path = self.workspaces[name]
        data_file = os.path.join(workspace_path, WORKSPACE_DATA_FILE_NAME)
        
        try:
            is_encrypted = self._is_encrypted_file(data_file)
            
            if is_encrypted:
                password = self._prompt_password(f"Enter password for '{name}'")
                if not password:
                    return None
                
                try:
                    workspace_data = FileManager.load_encrypted(data_file, password)
                    workspace = Workspace.from_dict(workspace_data)
                    workspace._password = password
                except InvalidToken:
                    print("Incorrect password or corrupted file")
                    return None
            else:
                workspace_data = FileManager.load_json(data_file)
                workspace = Workspace.from_dict(workspace_data)
                
                if workspace._password:
                    password = self._prompt_password(f"Enter password for '{name}'")
                    if not password or not workspace.check_password(password):
                        print("Incorrect password")
                        return None
            
            self.current_workspace = workspace
            print(f"Opened workspace: {name}")
            return workspace
            
        except Exception as e:
            print(f"Error opening workspace: {e}")
            return None
    
    def save_current_workspace(self) -> bool:
        """Save the current workspace to file."""
        if not self.current_workspace:
            print("No workspace to save")
            return False
        
        workspace = self.current_workspace
        workspace_path = self.workspaces[workspace.name]
        data_file = os.path.join(workspace_path, WORKSPACE_DATA_FILE_NAME)
        
        try:
            workspace_data = workspace.to_dict()
            
            if workspace._password:
                FileManager.save_encrypted(workspace_data, data_file, workspace._password)
                print(f"Saved workspace (encrypted): {workspace.name}")
            else:
                FileManager.save_json(workspace_data, data_file)
                print(f"Saved workspace (plain): {workspace.name}")
            
            return True
            
        except Exception as e:
            print(f"Error saving workspace: {e}")
            return False
    
    def close_current_workspace(self):
        """Close the current workspace."""
        if self.current_workspace:
            print(f"Closed workspace: {self.current_workspace.name}")
            self.current_workspace = None
        else:
            print("No workspace to close")
    
    def list_workspaces(self) -> ListType[str]:
        """Get list of available workspace names."""
        return list(self.workspaces.keys())

def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def run_cli():
    """Run the interactive CLI."""
    manager = WorkspaceManager()
    
    print("Welcome to Workspace Manager!")
    print(f"Workspaces directory: ./{DEFAULT_WORKSPACES_DIR}/")
    input("Press Enter to continue...")
    
    manager.load_config()
    
    while True:
        clear_screen()
        
        print("\n=== Workspace Manager ===")
        if manager.current_workspace:
            status = "Protected" if manager.current_workspace._password else "Unprotected"
            print(f"Current workspace: '{manager.current_workspace.name}' ({status})")
        else:
            print("No workspace open")
        
        print("\nOptions:")
        print("1. List workspaces")
        print("2. Open workspace")
        print("3. Create workspace")
        print("4. Change password")
        print("5. Save workspace")
        print("6. Close workspace")
        print("7. Show workspace data")
        print("0. Exit")
        
        choice = input("\nEnter choice: ").strip()
        
        if choice == '1':
            workspaces = manager.list_workspaces()
            if workspaces:
                print("\nAvailable workspaces:")
                for name in workspaces:
                    print(f"  - {name}")
            else:
                print("No workspaces available")
        
        elif choice == '2':
            workspaces = manager.list_workspaces()
            if not workspaces:
                print("No workspaces available")
            else:
                print("\nWorkspaces:")
                for i, name in enumerate(workspaces, 1):
                    print(f"  {i}. {name}")
                
                selection = input("\nEnter name or number: ").strip()
                
                if selection.isdigit():
                    idx = int(selection) - 1
                    if 0 <= idx < len(workspaces):
                        selection = workspaces[idx]
                
                if selection in workspaces:
                    if manager.current_workspace:
                        manager.close_current_workspace()
                    manager.open_workspace(selection)
        
        elif choice == '3':
            name = input("Enter workspace name: ").strip()
            if name:
                manager.create_workspace(name)
        
        elif choice == '4':
            if not manager.current_workspace:
                print("No workspace open")
            else:
                ws = manager.current_workspace
                
                old_password = ""
                if ws._password:
                    old_password = input("Enter current password: ").strip()
                
                new_password = input("Enter new password (empty to remove): ").strip()
                
                if ws.set_password(new_password, old_password):
                    print("Password updated")
                    manager.save_current_workspace()
                else:
                    print("Password change failed")
        
        elif choice == '5':
            manager.save_current_workspace()
        
        elif choice == '6':
            manager.close_current_workspace()
        
        elif choice == '7':
            if manager.current_workspace:
                try:
                    data = manager.current_workspace.to_dict()
                    print("\nWorkspace data:")
                    print(json.dumps(data, indent=2))
                except Exception as e:
                    print(f"Error displaying data: {e}")
            else:
                print("No workspace open")
        
        elif choice == '0':
            clear_screen()
            print("Goodbye!")
            if manager.current_workspace:
                manager.close_current_workspace()
            break
        
        else:
            print("Invalid choice")
        
        if choice != '0':
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    run_cli()
