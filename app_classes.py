import os
import json
import datetime
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64

# Configuration
CONFIG_FILE_NAME = "workspaces.json"
WORKSPACE_DATA_FILE_NAME = "workspace.data"
DEFAULT_WORKSPACES_DIR = "workspaces"
MAX_PASSWORD_ATTEMPTS = 3
SALT_SIZE = 16
KDF_ITERATIONS = 100_000

# Encryption utilities
def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive encryption key from password and salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
        backend=default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))

def _encrypt_data(data: str, password: str) -> bytes:
    """Encrypt data with password."""
    salt = os.urandom(SALT_SIZE)
    key = _derive_key(password, salt)
    encrypted = Fernet(key).encrypt(data.encode('utf-8'))
    return salt + encrypted

def _decrypt_data(encrypted_data: bytes, password: str) -> str:
    """Decrypt data with password."""
    if len(encrypted_data) <= SALT_SIZE:
        raise ValueError("Invalid encrypted data")
    
    salt = encrypted_data[:SALT_SIZE]
    ciphertext = encrypted_data[SALT_SIZE:]
    key = _derive_key(password, salt)
    
    return Fernet(key).decrypt(ciphertext).decode('utf-8')

class Board:
    """Simple board class for workspace."""
    def __init__(self, name="Default Board"):
        self.name = name
        self.lists = []
    
    def to_dict(self):
        return {"name": self.name, "lists_count": len(self.lists)}
    
    @classmethod
    def from_dict(cls, data):
        return cls(name=data.get("name", "Default Board"))

class Workspace:
    """Represents a workspace with optional password protection."""
    def __init__(self, name, password=None):
        self.name = name
        self._password = password
        self.last_edited = datetime.datetime.now(datetime.timezone.utc)
        self.board = Board(f"{name}'s Board")
    
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
            "board": self.board.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create workspace from dictionary."""
        ws = cls(data.get("name", "Unnamed"))
        ws._password = data.get("password")
        
        # Handle last_edited
        if data.get("last_edited"):
            try:
                ws.last_edited = datetime.datetime.fromisoformat(data["last_edited"])
            except ValueError:
                pass  # Keep default time
        
        # Handle board
        if data.get("board"):
            ws.board = Board.from_dict(data["board"])
        
        return ws

class WorkspaceManager:
    """Manages multiple workspaces."""
    def __init__(self):
        self.config_file = CONFIG_FILE_NAME
        self.workspaces = {}  # name -> path mapping
        self.current_workspace = None
    
    def _print(self, message):
        """Print message to console."""
        print(message)
    
    def _save_config(self):
        """Save workspace configuration to file."""
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.workspaces, f, indent=2)
        except IOError as e:
            self._print(f"Error saving config: {e}")
    
    def load_workspaces(self):
        """Load workspace configuration from file."""
        if not os.path.exists(self.config_file):
            self.workspaces = {}
            self._print(f"No config file found. Creating {self.config_file}")
            self._save_config()
            return
        
        try:
            with open(self.config_file, "r") as f:
                self.workspaces = json.load(f)
            
            # Clean up invalid entries
            valid_workspaces = {}
            for name, path in self.workspaces.items():
                data_file = os.path.join(path, WORKSPACE_DATA_FILE_NAME)
                if os.path.isdir(path) and os.path.exists(data_file):
                    valid_workspaces[name] = path
                else:
                    self._print(f"Removing invalid workspace: {name}")
            
            if len(valid_workspaces) != len(self.workspaces):
                self.workspaces = valid_workspaces
                self._save_config()
                
        except (json.JSONDecodeError, IOError) as e:
            self._print(f"Error loading config: {e}. Starting fresh.")
            self.workspaces = {}
            self._save_config()
    
    def create_workspace(self, name, parent_dir=DEFAULT_WORKSPACES_DIR):
        """Create a new workspace."""
        if not name or name in self.workspaces:
            self._print(f"Invalid or duplicate workspace name: {name}")
            return None
        
        workspace_path = os.path.join(parent_dir, name)
        if os.path.exists(workspace_path):
            self._print(f"Directory already exists: {workspace_path}")
            return None
        
        try:
            os.makedirs(workspace_path, exist_ok=True)
            
            # Create workspace and save it
            workspace = Workspace(name)
            data_file = os.path.join(workspace_path, WORKSPACE_DATA_FILE_NAME)
            
            with open(data_file, "w") as f:
                json.dump(workspace.to_dict(), f, indent=2)
            
            self.workspaces[name] = workspace_path
            self._save_config()
            
            self._print(f"Created workspace: {name}")
            return workspace
            
        except OSError as e:
            self._print(f"Error creating workspace: {e}")
            return None
    
    def _load_workspace_data(self, workspace_path):
        """Load workspace data from file (plain or encrypted)."""
        data_file = os.path.join(workspace_path, WORKSPACE_DATA_FILE_NAME)
        
        # Try plain JSON first
        try:
            with open(data_file, "r") as f:
                return json.load(f), False  # data, is_encrypted
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        
        # Try encrypted
        try:
            with open(data_file, "rb") as f:
                encrypted_data = f.read()
            return encrypted_data, True  # encrypted_bytes, is_encrypted
        except IOError as e:
            raise Exception(f"Cannot read workspace data: {e}")
    
    def _prompt_password(self, prompt_text):
        """Prompt for password with retry logic."""
        for attempt in range(MAX_PASSWORD_ATTEMPTS):
            password = input(f"{prompt_text} (attempt {attempt + 1}/{MAX_PASSWORD_ATTEMPTS}, 'CANCEL' to abort): ").strip()
            
            if password == "CANCEL":
                return None
            
            if password:  # Non-empty password
                return password
            
            self._print("Password cannot be empty")
        
        self._print("Maximum attempts reached")
        return None
    
    def open_workspace(self, name):
        """Open a workspace by name."""
        if name not in self.workspaces:
            self._print(f"Workspace not found: {name}")
            return None
        
        workspace_path = self.workspaces[name]
        
        try:
            data, is_encrypted = self._load_workspace_data(workspace_path)
            
            if is_encrypted:
                # Decrypt the data
                password = self._prompt_password(f"Enter password for '{name}'")
                if not password:
                    return None
                
                try:
                    decrypted_json = _decrypt_data(data, password)
                    workspace_data = json.loads(decrypted_json)
                    workspace = Workspace.from_dict(workspace_data)
                    workspace._password = password  # Store the password
                    
                except InvalidToken:
                    self._print("Incorrect password or corrupted file")
                    return None
            else:
                # Plain JSON data
                workspace = Workspace.from_dict(data)
                
                # Check if workspace requires password
                if workspace._password:
                    password = self._prompt_password(f"Enter password for '{name}'")
                    if not password or not workspace.check_password(password):
                        self._print("Incorrect password")
                        return None
            
            self.current_workspace = workspace
            self._print(f"Opened workspace: {name}")
            return workspace
            
        except Exception as e:
            self._print(f"Error opening workspace: {e}")
            return None
    
    def save_current_workspace(self):
        """Save the current workspace to file."""
        if not self.current_workspace:
            self._print("No workspace to save")
            return False
        
        workspace = self.current_workspace
        workspace_path = self.workspaces[workspace.name]
        data_file = os.path.join(workspace_path, WORKSPACE_DATA_FILE_NAME)
        
        try:
            workspace_data = workspace.to_dict()
            
            if workspace._password:
                # Save encrypted
                json_data = json.dumps(workspace_data, indent=2)
                encrypted_data = _encrypt_data(json_data, workspace._password)
                
                with open(data_file, "wb") as f:
                    f.write(encrypted_data)
                
                self._print(f"Saved workspace (encrypted): {workspace.name}")
            else:
                # Save as plain JSON
                with open(data_file, "w") as f:
                    json.dump(workspace_data, f, indent=2)
                
                self._print(f"Saved workspace (plain): {workspace.name}")
            
            return True
            
        except Exception as e:
            self._print(f"Error saving workspace: {e}")
            return False
    
    def close_current_workspace(self):
        """Close the current workspace."""
        if self.current_workspace:
            self._print(f"Closed workspace: {self.current_workspace.name}")
            self.current_workspace = None
        else:
            self._print("No workspace to close")

def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def run_cli():
    """Run the interactive CLI."""
    manager = WorkspaceManager()
    os.makedirs(DEFAULT_WORKSPACES_DIR, exist_ok=True)
    
    print("Welcome to Workspace Manager!")
    print(f"Workspaces directory: ./{DEFAULT_WORKSPACES_DIR}/")
    input("Press Enter to continue...")
    
    manager.load_workspaces()
    
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
            if manager.workspaces:
                print("\nAvailable workspaces:")
                for name, path in manager.workspaces.items():
                    print(f"  - {name} ({path})")
            else:
                print("No workspaces available")
        
        elif choice == '2':
            if not manager.workspaces:
                print("No workspaces available")
            else:
                print("\nWorkspaces:")
                names = list(manager.workspaces.keys())
                for i, name in enumerate(names, 1):
                    print(f"  {i}. {name}")
                
                selection = input("\nEnter name or number: ").strip()
                
                if selection.isdigit():
                    idx = int(selection) - 1
                    if 0 <= idx < len(names):
                        selection = names[idx]
                
                if selection in manager.workspaces:
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
