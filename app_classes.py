import os
import json
import datetime
import base64
import shutil
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

# --- Configuration ---
DEFAULT_WORKSPACES_DIR = "workspaces"
CONFIG_FILE_NAME = "workspaces.json" # Now lives outside the workspaces dir
DATA_FILE_NAME = "data.json"
MAX_PASSWORD_ATTEMPTS = 3
SALT_SIZE = 16

class EncryptionHelper:
    """Handles encryption and decryption operations using Fernet."""
    @staticmethod
    def derive_key(password, salt):
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
        salt = os.urandom(SALT_SIZE)
        key = EncryptionHelper.derive_key(password, salt)
        encrypted = Fernet(key).encrypt(data_str.encode('utf-8'))
        return salt + encrypted

    @staticmethod
    def decrypt(encrypted_data, password):
        if len(encrypted_data) <= SALT_SIZE:
            raise ValueError("Invalid encrypted data: too short for salt.")
        salt = encrypted_data[:SALT_SIZE]
        ciphertext = encrypted_data[SALT_SIZE:]
        key = EncryptionHelper.derive_key(password, salt)
        return Fernet(key).decrypt(ciphertext).decode('utf-8')

class Board:
    """A simple data container for a board's state."""
    def __init__(self, name="Default Board", lists=None):
        self.name = name
        self.lists = lists if lists is not None else []

    def to_dict(self):
        return {"name": self.name, "lists": self.lists}

    @classmethod
    def from_dict(cls, data):
        return cls(name=data.get("name"), lists=data.get("lists", []))

class Workspace:
    """Represents a workspace, containing a board and its metadata."""
    def __init__(self, name, password=None, path=None):
        self.name = name
        self.path = path
        self._password = password
        self.last_edited = datetime.datetime.now().astimezone()
        self.board = Board(name=f"{name} Board")
        
    def set_password(self, new_password):
        self._password = new_password.strip() if new_password else None
        print(f"\nPassword has been {'set' if self._password else 'cleared'} for this session. "
              "Save the workspace to apply the change permanently.")

    def to_dict(self):
        return {
            "name": self.name,
            "last_edited": self.last_edited.isoformat(),
            "board": self.board.to_dict(),
        }

    @classmethod
    def from_dict(cls, data, path):
        workspace = cls(name=data.get("name", "Unnamed"), path=path)
        if last_edited_str := data.get("last_edited"):
            try:
                workspace.last_edited = datetime.datetime.fromisoformat(last_edited_str)
            except ValueError:
                pass
        if board_data := data.get("board"):
            workspace.board = Board.from_dict(board_data)
        return workspace

class WorkspaceManager:
    """The main controller for creating, opening, and saving workspaces."""
    def __init__(self, config_path=CONFIG_FILE_NAME, workspaces_dir=DEFAULT_WORKSPACES_DIR):
        self.workspaces_dir = workspaces_dir
        self.config_path = config_path
        self.workspaces = {}
        self.current_workspace = None
        os.makedirs(self.workspaces_dir, exist_ok=True)
        self._load_master_config()

    def _load_master_config(self):
        if not os.path.exists(self.config_path):
            self.workspaces = {}
            return
        try:
            with open(self.config_path, "r") as f:
                self.workspaces = json.load(f)
            self._clean_invalid_workspaces()
        except (IOError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load config file: {e}. Starting fresh.")
            self.workspaces = {}

    def _save_master_config(self):
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.workspaces, f, indent=2)
        except IOError as e:
            print(f"Error: Could not save master config: {e}")

    def _clean_invalid_workspaces(self):
        initial_count = len(self.workspaces)
        self.workspaces = {
            name: path for name, path in self.workspaces.items()
            if os.path.isdir(path) and os.path.exists(os.path.join(path, DATA_FILE_NAME))
        }
        if len(self.workspaces) != initial_count:
            self._save_master_config()

    def create_workspace(self, name):
        if not name or name in self.workspaces:
            print(f"\nError: Invalid or duplicate workspace name '{name}'.")
            return None
        
        path = os.path.join(self.workspaces_dir, name)
        if os.path.exists(path):
            print(f"\nError: Directory '{path}' already exists.")
            return None

        try:
            os.makedirs(path)
            workspace = Workspace(name, path=path)
            self.current_workspace = workspace
            self.save_current_workspace()
            
            self.workspaces[name] = path
            self._save_master_config()
            print(f"\nSuccessfully created and opened workspace: {name}")
            return workspace
        except OSError as e:
            print(f"\nError creating workspace: {e}")
            return None

    def open_workspace(self, name):
        if self.current_workspace:
            print(f"\nPlease close the current workspace ('{self.current_workspace.name}') first.")
            return None
        if name not in self.workspaces:
            print(f"\nError: Workspace '{name}' not found.")
            return None
        
        path = self.workspaces[name]
        data_path = os.path.join(path, DATA_FILE_NAME)
        password = None
        
        try:
            is_encrypted = False
            with open(data_path, 'rb') as f:
                try:
                    json.loads(f.read().decode('utf-8'))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    is_encrypted = True

            if is_encrypted:
                password = self._prompt_password(f"Enter password for '{name}'")
                if not password: return None

            with open(data_path, "rb") as f:
                file_content = f.read()
            
            data_str = EncryptionHelper.decrypt(file_content, password) if password else file_content.decode('utf-8')
            workspace_data = json.loads(data_str)

            workspace = Workspace.from_dict(workspace_data, path)
            workspace._password = password
            self.current_workspace = workspace
            print(f"\nSuccessfully opened workspace: {name}")
            return workspace

        except InvalidToken:
            print("\nError: Incorrect password or corrupted data file.")
        except (IOError, json.JSONDecodeError, ValueError) as e:
            print(f"\nError opening workspace '{name}': {e}")
        return None

    def save_current_workspace(self):
        if not self.current_workspace:
            print("\nNo active workspace to save.")
            return

        ws = self.current_workspace
        ws.last_edited = datetime.datetime.now(datetime.timezone.utc)
        data_path = os.path.join(ws.path, DATA_FILE_NAME)
        json_data = json.dumps(ws.to_dict(), indent=2)

        try:
            if ws._password:
                encrypted_data = EncryptionHelper.encrypt(json_data, ws._password)
                with open(data_path, "wb") as f:
                    f.write(encrypted_data)
            else:
                with open(data_path, "w", encoding='utf-8') as f:
                    f.write(json_data)
            print(f"\nWorkspace '{ws.name}' saved successfully.")
        except IOError as e:
            print(f"\nError saving workspace: {e}")
    
    def close_current_workspace(self):
        if not self.current_workspace:
            print("\nNo workspace is currently open.")
            return
        name = self.current_workspace.name
        self.current_workspace = None
        print(f"\nWorkspace '{name}' has been closed.")

    def list_workspaces(self):
        return list(self.workspaces.keys())

    def _prompt_password(self, prompt_text):
        for attempt in range(MAX_PASSWORD_ATTEMPTS):
            prompt = f"{prompt_text} (attempt {attempt + 1}/{MAX_PASSWORD_ATTEMPTS}, type 'CANCEL' to abort): "
            password = input(prompt).strip()
            if password.upper() == "CANCEL": return None
            if password: return password
            print("Password cannot be empty.")
        print("\nMaximum password attempts reached.")
        return None

# --- CLI Test Function ---
# def clear_console():
#     """Clears the console screen."""
#     os.system('cls' if os.name == 'nt' else 'clear')
#
# def test_cli():
#     """Runs an interactive command-line interface to test the WorkspaceManager."""
#     manager = WorkspaceManager()
#     clear_console()
    
#     while True:
#         print("="*50)
#         status = f"Current Workspace: {manager.current_workspace.name if manager.current_workspace else 'None'}"
#         print(f"MENU\t\t{status}")
#         print("-"*50)
#         print("  list            - List all workspaces")
#         print("  create <name>   - Create a new workspace")
#         print("  open <name>     - Open a workspace")
#         print("  close           - Close the current workspace")
#         print("  save            - Save the current workspace")
#         print("  view            - View the current workspace's board")
#         print("  addlist <name>  - Add a list to the current board")
#         print("  password <pass> - Set/change password for the open workspace")
#         print("  clear           - Clear the console screen")
#         print("  cleanup         - DELETE all workspaces and config")
#         print("  quit            - Exit the program")
#         print("="*50)
        
#         command_line = input("> ").strip().lower().split(maxsplit=1)
#         if not command_line:
#             continue
            
#         cmd = command_line[0]
#         args = command_line[1] if len(command_line) > 1 else ""

#         # --- Command Processing ---
#         if cmd == 'quit':
#             break
#         elif cmd == 'list':
#             workspaces = manager.list_workspaces()
#             if not workspaces:
#                 print("\nNo workspaces found.")
#             else:
#                 print("\nAvailable workspaces:")
#                 for ws in workspaces:
#                     print(f"- {ws}")
#         elif cmd == 'create':
#             if not args: print("Usage: create <workspace_name>")
#             else: manager.create_workspace(args)
#         elif cmd == 'open':
#             if not args: print("Usage: open <workspace_name>")
#             else: manager.open_workspace(args)
#         elif cmd == 'close':
#             manager.close_current_workspace()
#         elif cmd == 'save':
#             manager.save_current_workspace()
#         elif cmd == 'view':
#             if manager.current_workspace:
#                 print(json.dumps(manager.current_workspace.board.to_dict(), indent=2))
#             else:
#                 print("\nNo workspace is open.")
#         elif cmd == 'addlist':
#             if not manager.current_workspace:
#                 print("\nNo workspace is open.")
#             elif not args:
#                 print("Usage: addlist <list_name>")
#             else:
#                 manager.current_workspace.board.lists.append({"name": args, "cards": []})
#                 print(f"\nAdded list '{args}'. Don't forget to save.")
#         elif cmd == 'password':
#             if not manager.current_workspace:
#                 print("\nNo workspace is open.")
#             else:
#                 manager.current_workspace.set_password(args)
#         elif cmd == 'clear':
#             clear_console()
#             continue
#         elif cmd == 'cleanup':
#             confirm = input("This will DELETE ALL workspaces and data. Are you sure? (y/n): ").lower()
#             if confirm == 'y':
#                 manager.close_current_workspace()
#                 try:
#                     shutil.rmtree(manager.workspaces_dir)
#                     print(f"Removed directory: {manager.workspaces_dir}")
#                 except FileNotFoundError: pass
#                 try:
#                     os.remove(manager.config_path)
#                     print(f"Removed config file: {manager.config_path}")
#                 except FileNotFoundError: pass
                
#                 print("\nCleanup successful.")
#                 manager = WorkspaceManager()
#         else:
#             print("\nUnknown command.")

#         # --- Wait for user and clear screen ---
#         input("\nPress Enter to continue...")
#         clear_console()


# if __name__ == "__main__":
#     test_cli()