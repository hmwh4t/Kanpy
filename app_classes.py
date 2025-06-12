import os
import json
import datetime
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64

# Configuration
DEFAULT_WORKSPACES_DIR = "workspaces"
CONFIG_FILE_NAME = "workspaces.json"
WORKSPACE_DATA_FILE_NAME = "workspace.data"
BOARD_DATA_FILE_NAME = "board.data"
MAX_PASSWORD_ATTEMPTS = 3
SALT_SIZE = 16
KDF_ITERATIONS = 100000

class EncryptionHelper():
    """Handles encryption and decryption operations."""
    
    @staticmethod
    def derive_key(password, salt):
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
    def encrypt(data, password):
        """Encrypt data with password."""
        salt = os.urandom(SALT_SIZE)
        key = EncryptionHelper.derive_key(password, salt)
        encrypted = Fernet(key).encrypt(data.encode('utf-8'))
        return salt + encrypted
    
    @staticmethod
    def decrypt(encrypted_data, password):
        """Decrypt data with password."""
        if len(encrypted_data) <= SALT_SIZE:
            raise ValueError("Invalid encrypted data")
        
        salt = encrypted_data[:SALT_SIZE]
        ciphertext = encrypted_data[SALT_SIZE:]
        key = EncryptionHelper.derive_key(password, salt)
        
        return Fernet(key).decrypt(ciphertext).decode('utf-8')

class Board():
    """Represents a board within a workspace."""

    def __init__(self, name="Default Board", workspace_path=None):
        self.name = name
        self.lists = []
        self.workspace_path = workspace_path  # Store the path

    def _get_board_data_path(self):
        """Helper to get the full path to the board.data file."""
        if not self.workspace_path:
            return None
        return os.path.join(self.workspace_path, BOARD_DATA_FILE_NAME)

    def load_config(self):
        """Load board configuration from a standard JSON file."""
        board_file_path = self._get_board_data_path()
        if not board_file_path or not os.path.exists(board_file_path):
            self.lists = []
            return

        try:
            # Use the standard JSON loader
            with open(board_file_path, "r") as f:
                data = json.load(f)
            # Populate the object from the loaded dictionary
            self.name = data.get("name", "Default Board")
            self.lists = data.get("lists", [])
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading board.data: {e}. Starting fresh.")
            self.lists = []

    def save_config(self):
        """Save board configuration to a standard JSON file."""
        board_file_path = self._get_board_data_path()
        if not board_file_path:
            print("Error: Cannot save board, workspace path not set.")
            return

        # Create a dictionary representing the board's state
        data_to_save = self.to_dict()

        try:
            # Use the standard JSON dumper with indentation
            with open(board_file_path, "w") as f:
                json.dump(data_to_save, f, indent=2)
        except IOError as e:
            print(f"Error saving board.data: {e}")

    def to_dict(self):
        """Convert board to a standard dictionary."""
        return {"name": self.name, "lists": self.lists}

    @classmethod
    def from_dict(cls, data, workspace_path=None):
        """Create a Board instance from a dictionary."""
        board = cls(name=data.get("name"), workspace_path=workspace_path)
        board.lists = data.get("lists", [])
        return board

class Workspace():
    """Represents a workspace with optional password protection."""

    # Add path to the constructor
    def __init__(self, name, password=None, path=None):
        self.name = name
        self._password = password
        self.path = path  # Store the workspace's own path
        self.last_edited = datetime.datetime.now(datetime.timezone.utc)
        # Create the board and pass the path to it
        self.board = Board(name=f"{name} Board", workspace_path=self.path)

    def check_password(self, password):
        """Check if password is correct."""
        if not self._password:
            return not password
        return self._password == password

    def set_password(self, new_password, old_password=None):
        """Set or change workspace password."""
        if self._password and self._password != old_password:
            return False

        self._password = new_password.strip() if new_password else None
        self.last_edited = datetime.datetime.now(datetime.timezone.utc)
        return True

    def to_dict(self):
        """Convert workspace to dictionary."""
        return {
            "name": self.name,
            "password": self._password,
            "last_edited": self.last_edited.isoformat(),
            # Serialize the board object using its own method
            "board": self.board.to_dict() if self.board else None,
        }

    @classmethod
    def from_dict(cls, data, path=None):  # Accept path here
        """Create workspace from dictionary."""
        # Pass the path to the constructor
        workspace = cls(data.get("name", "Unnamed"), path=path)
        workspace._password = data.get("password")

        if data.get("last_edited"):
            try:
                # Simplified datetime parsing
                workspace.last_edited = datetime.datetime.fromisoformat(
                    data["last_edited"]
                )
            except (ValueError, KeyError):
                pass  # Keep default time

        # Load board data from the dictionary and re-instantiate the Board
        board_data = data.get("board")
        if board_data:
            workspace.board = Board.from_dict(board_data, workspace_path=path)
        
        # Now that the workspace and board exist, load the board's data
        # from its separate file (board.data)
        workspace.board.load_config()

        return workspace

class FileManager():
    """Handles file operations for workspaces."""
    
    @staticmethod
    def load_json(file_path):
        """Load JSON data from file."""
        with open(file_path, "r") as f:
            return json.load(f)
    
    @staticmethod
    def save_json(data, file_path):
        """Save JSON data to file."""
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)
    
    @staticmethod
    def load_encrypted(file_path, password):
        """Load encrypted data from file."""
        with open(file_path, "rb") as f:
            encrypted_data = f.read()
        
        decrypted_json = EncryptionHelper.decrypt(encrypted_data, password)
        return json.loads(decrypted_json)
    
    @staticmethod
    def save_encrypted(data, file_path, password):
        """Save encrypted data to file."""
        json_data = json.dumps(data, indent=2)
        encrypted_data = EncryptionHelper.encrypt(json_data, password)
        
        with open(file_path, "wb") as f:
            f.write(encrypted_data)

class WorkspaceManager():
    # ... (no changes to __init__, load_config, save_config, _clean_invalid_workspaces) ...
    
    def __init__(self, workspaces_dir=DEFAULT_WORKSPACES_DIR):
        self.workspaces_dir = workspaces_dir
        self.config_file = os.path.join(self.workspaces_dir, CONFIG_FILE_NAME) # Place config inside workspaces dir
        self.workspaces = {}  # name -> path mapping
        self.current_workspace = None
        
        # Ensure workspaces directory exists
        try:
            os.makedirs(self.workspaces_dir, exist_ok=True)
        except OSError:
            pass  # Directory already exists

    def load_config(self):
        """Load workspace configuration from file."""
        if not os.path.exists(self.config_file):
            self.workspaces = {}
            self.save_config()
            return
        
        try:
            self.workspaces = FileManager.load_json(self.config_file)
            self._clean_invalid_workspaces()
        except (ValueError, IOError) as e:
            print("Error loading config: {}. Starting fresh.".format(e))
            self.workspaces = {}
            self.save_config()

    def save_config(self):
        """Save workspace configuration to file."""
        try:
            FileManager.save_json(self.workspaces, self.config_file)
        except IOError as e:
            print("Error saving config: {}".format(e))

    def _clean_invalid_workspaces(self):
        """Remove invalid workspace entries from config."""
        valid_workspaces = {}
        for name, path in self.workspaces.items():
            data_file = os.path.join(path, WORKSPACE_DATA_FILE_NAME)
            if os.path.isdir(path) and os.path.exists(data_file):
                valid_workspaces[name] = path
            else:
                print("Removing invalid workspace: {}".format(name))
        
        if len(valid_workspaces) != len(self.workspaces):
            self.workspaces = valid_workspaces
            self.save_config()

    def create_workspace(self, name):
        """Create a new workspace."""
        if not name or name in self.workspaces:
            print("Invalid or duplicate workspace name: {}".format(name))
            return None

        workspace_path = os.path.join(self.workspaces_dir, name)
        if os.path.exists(workspace_path):
            print("Directory already exists: {}".format(workspace_path))
            return None

        try:
            os.makedirs(workspace_path, exist_ok=True)

            # Create workspace and pass its path to it
            workspace = Workspace(name, path=workspace_path)
            data_file = os.path.join(workspace_path, WORKSPACE_DATA_FILE_NAME)

            # Save the main workspace.data file
            FileManager.save_json(workspace.to_dict(), data_file)
            # Also save the initial board.data file
            workspace.board.save_config()

            self.workspaces[name] = workspace_path
            self.save_config()

            print("Created workspace: {}".format(name))
            return workspace

        except OSError as e:
            print("Error creating workspace: {}".format(e))
            return None

    # ... (_is_encrypted_file and _prompt_password are unchanged) ...
    def _is_encrypted_file(self, file_path):
        """Check if file contains encrypted data."""
        try:
            FileManager.load_json(file_path)
            return False
        except (ValueError, UnicodeDecodeError):
            return True
    
    def _prompt_password(self, prompt_text):
        """Prompt for password with retry logic."""
        for attempt in range(MAX_PASSWORD_ATTEMPTS):
            password = input("{} (attempt {}/{}, 'CANCEL' to abort): ".format(
                prompt_text, attempt + 1, MAX_PASSWORD_ATTEMPTS)).strip()
            
            if password == "CANCEL":
                return None
            
            if password:
                return password
            
            print("Password cannot be empty")
        
        print("Maximum attempts reached")
        return None

    def open_workspace(self, name):
        """Open a workspace by name."""
        if name not in self.workspaces:
            print("Workspace not found: {}".format(name))
            return None

        workspace_path = self.workspaces[name]
        data_file = os.path.join(workspace_path, WORKSPACE_DATA_FILE_NAME)

        try:
            is_encrypted = self._is_encrypted_file(data_file)
            workspace_data = None

            if is_encrypted:
                password = self._prompt_password(f"Enter password for '{name}'")
                if not password:
                    return None
                try:
                    workspace_data = FileManager.load_encrypted(data_file, password)
                    # Pass the path when creating from dict
                    workspace = Workspace.from_dict(workspace_data, path=workspace_path)
                    workspace._password = password
                except InvalidToken:
                    print("Incorrect password or corrupted file")
                    return None
            else:
                workspace_data = FileManager.load_json(data_file)
                # Pass the path when creating from dict
                workspace = Workspace.from_dict(workspace_data, path=workspace_path)
                if workspace._password:
                    password = self._prompt_password(f"Enter password for '{name}'")
                    if not password or not workspace.check_password(password):
                        print("Incorrect password")
                        return None

            self.current_workspace = workspace
            print("Opened workspace: {}".format(name))
            return workspace

        except Exception as e:
            print("Error opening workspace: {}".format(e))
            return None

    def save_current_workspace(self):
        """Save the current workspace to file."""
        if not self.current_workspace:
            print("No workspace to save")
            return False

        workspace = self.current_workspace
        # The workspace object now knows its own path
        workspace_path = workspace.path
        data_file = os.path.join(workspace_path, WORKSPACE_DATA_FILE_NAME)

        try:
            workspace_data = workspace.to_dict()

            if workspace._password:
                FileManager.save_encrypted(
                    workspace_data, data_file, workspace._password
                )
            else:
                FileManager.save_json(workspace_data, data_file)
            
            # Explicitly save the board's data too
            workspace.board.save_config()

            print("Saved workspace: {}".format(workspace.name))
            return True

        except Exception as e:
            print("Error saving workspace: {}".format(e))
            return False
    
    # ... (close_current_workspace and list_workspaces are unchanged) ...
    def close_current_workspace(self):
        """Close the current workspace."""
        if self.current_workspace:
            print("Closed workspace: {}".format(self.current_workspace.name))
            self.current_workspace = None
        else:
            print("No workspace to close")
    
    def list_workspaces(self):
        """Get list of available workspace names."""
        return list(self.workspaces.keys())

def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def run_cli():
    """Run the interactive CLI."""
    manager = WorkspaceManager()
    
    print("Welcome to Workspace Manager!")
    print("Workspaces directory: ./{}/".format(DEFAULT_WORKSPACES_DIR))
    input("Press Enter to continue...")
    
    manager.load_config()
    
    while True:
        clear_screen()
        
        print("\n=== Workspace Manager ===")
        if manager.current_workspace:
            status = "Protected" if manager.current_workspace._password else "Unprotected"
            print("Current workspace: '{}' ({})".format(manager.current_workspace.name, status))
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
                    print("  - {}".format(name))
            else:
                print("No workspaces available")
        
        elif choice == '2':
            workspaces = manager.list_workspaces()
            if not workspaces:
                print("No workspaces available")
            else:
                print("\nWorkspaces:")
                for i, name in enumerate(workspaces, 1):
                    print("  {}. {}".format(i, name))
                
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
                    print("Error displaying data: {}".format(e))
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
