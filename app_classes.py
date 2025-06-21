import os
import json
import datetime
import base64
import shutil
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

# === CONFIGURATION CONSTANTS ===
DEFAULT_WORKSPACES_DIR = "workspaces"
CONFIG_FILE_NAME = "workspaces.json"
DATA_FILE_NAME = "data.json"

# Security settings
MAX_PASSWORD_ATTEMPTS = 3
SALT_SIZE = 16


class EncryptionHelper:
    """
    Utility class for handling encryption and decryption operations.
    """
    
    @staticmethod
    def derive_key(password, salt):
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        derived_key = kdf.derive(password.encode('utf-8'))
        return base64.urlsafe_b64encode(derived_key)

    @staticmethod
    def encrypt(data_str, password):
        salt = os.urandom(SALT_SIZE)
        key = EncryptionHelper.derive_key(password, salt)
        fernet = Fernet(key)
        encrypted = fernet.encrypt(data_str.encode('utf-8'))
        return salt + encrypted

    @staticmethod
    def decrypt(encrypted_data, password):
        if len(encrypted_data) <= SALT_SIZE:
            raise ValueError("Invalid encrypted data: too short for salt.")
        
        salt = encrypted_data[:SALT_SIZE]
        ciphertext = encrypted_data[SALT_SIZE:]
        
        key = EncryptionHelper.derive_key(password, salt)
        fernet = Fernet(key)
        return fernet.decrypt(ciphertext).decode('utf-8')


class Card:
    """
    Represents a task card.
    """
    def __init__(self, name, description="No description provided", deadline=None, priority=0):
        self.name = name
        self.description = description
        self.deadline = deadline
        self.priority = priority
        self.completed = False

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data):
        card = cls(
            name=data.get("name", "Untitled Card"),
            description=data.get("description", "No description provided"),
            deadline=data.get("deadline", None),
            priority=data.get("priority", 0)
        )
        card.completed = data.get("completed", False)
        return card


class ListObject:
    """
    A container for managing cards within a list.
    """
    def __init__(self, name="Untitled List", description="No description provided", cards=None):
        self.name = name
        self.description = description
        self._cards = [Card.from_dict(c) for c in cards] if cards else []

    def cards(self):
        return [card.to_dict() for card in self._cards]

    def add_card(self, card_obj):
        if not isinstance(card_obj, Card):
            raise TypeError("Can only add Card objects to a list.")
        self._cards.append(card_obj)

    def delete_card(self, card_name):
        card_to_delete = next((c for c in self._cards if c.name.lower() == card_name.lower()), None)
        if card_to_delete:
            self._cards.remove(card_to_delete)
            return card_to_delete
        return None

    def to_dict(self):
        return {"name": self.name, "description": self.description, "cards": self.cards()}
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data.get("name", "Untitled List"),
            description=data.get("description", "No description provided"),
            cards=data.get("cards", [])
        )


class Bin:
    """
    Recycle bin for storing deleted items.
    """
    def __init__(self):
        self._deleted_cards = []
        self._deleted_lists = []

    def add_card(self, card, original_list_name):
        self._deleted_cards.append((card, original_list_name))

    def add_list(self, list_obj):
        self._deleted_lists.append(list_obj)

    def to_dict(self):
        return {
            "cards": [{"card": card.to_dict(), "original_list": list_name} for card, list_name in self._deleted_cards],
            "lists": [list_obj.to_dict() for list_obj in self._deleted_lists]
        }

    @classmethod
    def from_dict(cls, data):
        bin_instance = cls()
        if not data: return bin_instance
        for item in data.get("cards", []):
            if "card" in item and "original_list" in item:
                card = Card.from_dict(item["card"])
                bin_instance._deleted_cards.append((card, item["original_list"]))
        bin_instance._deleted_lists = [ListObject.from_dict(list_data) for list_data in data.get("lists", [])]
        return bin_instance


class Board:
    """
    A board containing multiple lists and a bin.
    """
    def __init__(self, name="Default Board", lists=None, bin_data=None):
        self.name = name
        self._list_objects = [ListObject.from_dict(ld) for ld in lists] if lists else []
        self.bin = Bin.from_dict(bin_data)

    def list_objects(self):
        return self._list_objects

    def find_list(self, list_name):
        return next((l for l in self._list_objects if l.name.lower() == list_name.lower()), None)
    
    def create_list(self, name, description=""):
        new_list = ListObject(name=name, description=description)
        self._list_objects.append(new_list)
        return new_list

    def to_dict(self):
        return {"name": self.name, "lists": [l.to_dict() for l in self._list_objects], "bin": self.bin.to_dict()}
    
    @classmethod
    def from_dict(cls, data):
        return cls(name=data.get("name", "Default Board"), lists=data.get("lists", []), bin_data=data.get("bin"))


class Workspace:
    """
    A workspace containing boards and metadata.
    """
    def __init__(self, name, password=None, path=None):
        self.name = name
        self.path = path
        self._password = password
        self.last_edited = datetime.datetime.now().astimezone()
        self._boards = [Board(name=f"{name} Board")]
        self._selected_board_index = 0

    def selected_board(self):
        if 0 <= self._selected_board_index < len(self._boards):
            return self._boards[self._selected_board_index]
        return None

    def set_password(self, new_password):
        self._password = new_password.strip() if new_password else None

    def has_password(self):
        return self._password is not None
        
    def update_last_edited(self):
        self.last_edited = datetime.datetime.now().astimezone()

    def to_dict(self):
        return {
            "name": self.name,
            "last_edited": self.last_edited.isoformat(),
            "boards": [board.to_dict() for board in self._boards],
            "selected_board_index": self._selected_board_index
        }

    @classmethod
    def from_dict(cls, data, path):
        workspace = cls(name=data.get("name", "Unnamed"), path=path)
        last_edited_str = data.get("last_edited")
        if last_edited_str:
            try: workspace.last_edited = datetime.datetime.fromisoformat(last_edited_str)
            except ValueError: workspace.last_edited = datetime.datetime.now(datetime.timezone.utc)
        boards_data = data.get("boards")
        if boards_data: workspace._boards = [Board.from_dict(b_data) for b_data in boards_data]
        workspace._selected_board_index = data.get("selected_board_index", 0)
        if workspace._selected_board_index >= len(workspace._boards): workspace._selected_board_index = 0
        return workspace


class WorkspaceManager:
    """
    Main controller for workspace operations.
    """
    def __init__(self, config_path="workspaces.json", workspaces_dir="workspaces"):
        self.workspaces_dir = workspaces_dir
        self.config_path = config_path
        self._workspaces_registry = {}
        self._current_workspace = None
        self._initialize()

    def _initialize(self):
        os.makedirs(self.workspaces_dir, exist_ok=True)
        self._load_master_config()

    def _load_master_config(self):
        if not os.path.exists(self.config_path):
            self._workspaces_registry = {}
            return
        try:
            with open(self.config_path, "r") as f:
                self._workspaces_registry = json.load(f)
            self._clean_invalid_workspaces()
        except (IOError, json.JSONDecodeError):
            self._workspaces_registry = {}

    def _save_master_config(self):
        try:
            with open(self.config_path, "w") as f:
                json.dump(self._workspaces_registry, f, indent=2)
        except IOError as e:
            print(f"Error saving master config: {e}")

    def _clean_invalid_workspaces(self):
        initial_count = len(self._workspaces_registry)
        # Updated to handle new registry structure
        self._workspaces_registry = {
            name: data for name, data in self._workspaces_registry.items()
            if isinstance(data, dict) and os.path.isdir(data.get("path")) and \
               os.path.exists(os.path.join(data.get("path"), "data.json"))
        }
        if len(self._workspaces_registry) != initial_count:
            self._save_master_config()

    def _is_file_encrypted(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                json.loads(f.read().decode('utf-8'))
            return False
        except (UnicodeDecodeError, json.JSONDecodeError, IOError):
            return True

    def current_workspace(self):
        return self._current_workspace

    def create_workspace(self, name):
        if not name or name in self._workspaces_registry: return None
        path = os.path.join(self.workspaces_dir, name)
        if os.path.exists(path): return None
        try:
            os.makedirs(path)
            workspace = Workspace(name, path=path)
            self._current_workspace = workspace
            # Update registry with new structure
            self._workspaces_registry[name] = {
                "path": path,
                "last_edited": workspace.last_edited.isoformat()
            }
            self.save_current_workspace() # This will also save the master config
            return workspace
        except OSError:
            return None

    def open_workspace(self, name, password=None):
        if self._current_workspace: return None
        if name not in self._workspaces_registry: return None
        
        path = self._workspaces_registry[name]["path"] # Updated
        data_path = os.path.join(path, "data.json")
        
        try:
            is_encrypted = self._is_file_encrypted(data_path)
            if is_encrypted and not password:
                return "password_required"

            with open(data_path, "rb") as f:
                file_content = f.read()
            
            data_str = EncryptionHelper.decrypt(file_content, password) if is_encrypted else file_content.decode('utf-8')
            
            workspace = Workspace.from_dict(json.loads(data_str), path)
            workspace._password = password
            self._current_workspace = workspace
            return workspace
        except InvalidToken:
            return None
        except (IOError, json.JSONDecodeError, ValueError):
            return None

    def save_current_workspace(self):
        if not self._current_workspace: return False
        workspace = self._current_workspace
        workspace.update_last_edited()
        
        # Save the individual workspace file
        data_path = os.path.join(workspace.path, "data.json")
        json_data = json.dumps(workspace.to_dict(), indent=2)
        try:
            if workspace.has_password():
                with open(data_path, "wb") as f: f.write(EncryptionHelper.encrypt(json_data, workspace._password))
            else:
                with open(data_path, "w", encoding='utf-8') as f: f.write(json_data)
        except IOError:
            return False
            
        # Update and save the master registry with the new timestamp
        if workspace.name in self._workspaces_registry:
            self._workspaces_registry[workspace.name]["last_edited"] = workspace.last_edited.isoformat()
            self._save_master_config()
            
        return True

    def close_current_workspace(self):
        self._current_workspace = None

    def list_workspaces(self):
        return list(self._workspaces_registry.keys())

    def workspaces(self):
        """Returns the full registry dictionary."""
        return self._workspaces_registry

    def workspace_exists(self, name):
        return name in self._workspaces_registry

    def is_workspace_encrypted(self, name):
        if name not in self._workspaces_registry: return False
        path = self._workspaces_registry[name]["path"] # Updated
        return self._is_file_encrypted(os.path.join(path, "data.json"))

    def delete_workspace(self, name):
        if name not in self._workspaces_registry: return False
        if self._current_workspace and self._current_workspace.name == name: return False
        
        path = self._workspaces_registry[name]["path"] # Updated
        try:
            shutil.rmtree(path)
            del self._workspaces_registry[name]
            self._save_master_config()
            return True
        except OSError:
            return False

    def rename_workspace(self, old_name, new_name, password=None):
        """
        Renames a workspace. Handles encrypted workspaces if a password is provided.
        """
        if not new_name or new_name in self._workspaces_registry or old_name not in self._workspaces_registry:
            print(f"Rename validation failed: new_name='{new_name}', old_name='{old_name}'")
            return False
        
        # Use the provided password to open the workspace.
        # The 'open_workspace' method already handles decryption.
        workspace = self.open_workspace(old_name, password=password)
        if not workspace or workspace == "password_required":
            print(f"Failed to open '{old_name}' for renaming. It might be encrypted without a password provided.")
            if self._current_workspace: self.close_current_workspace() # Ensure it's closed
            return False
        
        old_path = self._workspaces_registry[old_name]["path"]
        new_path = os.path.join(self.workspaces_dir, new_name)

        try:
            # Update the name in the workspace object and save it to the *old* path first.
            workspace.name = new_name
            self._current_workspace = workspace
            self.save_current_workspace()
            self.close_current_workspace() # IMPORTANT: Close before renaming the folder

            # Now, rename the directory itself
            os.rename(old_path, new_path)

            # Finally, update the registry with the new name and path
            registry_entry = self._workspaces_registry.pop(old_name)
            registry_entry["path"] = new_path
            self._workspaces_registry[new_name] = registry_entry
            self._save_master_config()
            
            print(f"Successfully renamed '{old_name}' to '{new_name}'")
            return True
        except Exception as e:
            print(f"An error occurred during rename: {e}")
            # Attempt to roll back if directory rename failed
            if not os.path.exists(old_path) and os.path.exists(new_path):
                os.rename(new_path, old_path)
            return False