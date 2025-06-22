import os
import json
import datetime
import base64
import shutil
from typing import Optional, List, Dict, Any, Union
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend


class EncryptionHelper:
    """Helper class for encrypting and decrypting data using password-based encryption."""
    
    # Constants for key derivation function (KDF)
    SALT_LENGTH = 16  # Size of the salt in bytes
    KEY_LENGTH = 32   # Desired key length in bytes
    ITERATIONS = 100000  # Number of iterations for PBKDF2, for security
    
    @staticmethod
    def derive_key(password: str, salt: bytes) -> bytes:
        """Derive an encryption key from a password and salt using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=EncryptionHelper.KEY_LENGTH,
            salt=salt,
            iterations=EncryptionHelper.ITERATIONS,
            backend=default_backend()
        )
        # Derive the key and encode it for use with Fernet
        return base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))
    
    @staticmethod
    def encrypt(data_str: str, password: str) -> bytes:
        """Encrypt a string using a password."""
        salt = os.urandom(EncryptionHelper.SALT_LENGTH)
        key = EncryptionHelper.derive_key(password, salt)
        encrypted_data = Fernet(key).encrypt(data_str.encode('utf-8'))
        # Prepend the salt to the encrypted data for later use in decryption
        return salt + encrypted_data
    
    @staticmethod
    def decrypt(encrypted_data: bytes, password: str) -> str:
        """Decrypt encrypted data using a password."""
        # Extract the salt from the beginning of the data
        salt = encrypted_data[:EncryptionHelper.SALT_LENGTH]
        ciphertext = encrypted_data[EncryptionHelper.SALT_LENGTH:]
        # Re-derive the key using the same password and salt
        key = EncryptionHelper.derive_key(password, salt)
        # Decrypt and decode the data
        return Fernet(key).decrypt(ciphertext).decode('utf-8')


class Card:
    """Represents a task card with name, description, deadline, and priority."""
    
    def __init__(self, name: str, description: str = "", deadline: Optional[str] = None, priority: int = 0):
        self.name = name
        self.description = description
        self.deadline = deadline
        self.priority = priority
        self.completed = False

    def is_overdue(self) -> bool:
        """Check if the card's deadline is in the past."""
        if not self.deadline:
            return False
        try:
            # Compare the deadline date with today's date
            deadline_date = datetime.datetime.strptime(self.deadline, '%Y-%m-%d %H:%M').date()
            return deadline_date < datetime.date.today()
        except (ValueError, TypeError):
            # Handle cases with invalid date format or type
            return False
    
    def get_priority_display(self) -> str:
        """Returns a string of exclamation marks based on the priority level."""
        return '!' * self.priority

    def to_dict(self) -> Dict[str, Any]:
        """Convert card object to a dictionary for serialization."""
        return self.__dict__
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Card':
        """Create a Card instance from a dictionary."""
        card = cls(
            name=data.get("name", "Untitled"),
            description=data.get("description", ""),
            deadline=data.get("deadline"),
            priority=data.get("priority", 0)
        )
        card.completed = data.get("completed", False)
        return card

class ListObject:
    """Represents a list (e.g., a column on a Kanban board) containing multiple cards."""
    
    def __init__(self, name: str = "Untitled List", description: str = "", cards: Optional[List[Dict[str, Any]]] = None):
        self.name = name
        self.description = description
        # Initialize cards from dictionary data if provided, otherwise start with an empty list
        self._cards = [Card.from_dict(card_data) for card_data in cards] if cards else []
    
    def cards(self) -> List[Card]:
        """Get all cards in this list."""
        return self._cards
    
    def add_card(self, card_obj: Card) -> None:
        """Add a card to this list."""
        self._cards.append(card_obj)
    
    def delete_card(self, card_obj_to_delete: Card) -> bool:
        """Delete a card from this list by object reference."""
        try:
            self._cards.remove(card_obj_to_delete)
            return True
        except ValueError:
            # Card was not found in the list, so deletion fails
            return False
    
    def _find_card_by_name(self, card_name: str) -> Optional[Card]:
        """Find a card in this list by its name."""
        return next((card for card in self._cards if card.name == card_name), None)

    def rename_list(self, new_name: str) -> bool:
        """Rename this list. Returns True if successful."""
        if new_name:
            self.name = new_name
            return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert list object to a dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "cards": [card.to_dict() for card in self._cards]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ListObject':
        """Create a ListObject instance from a dictionary."""
        return cls(
            name=data.get("name", "Untitled List"),
            description=data.get("description", ""),
            cards=data.get("cards", [])
        )


class Bin:
    """Represents a recycle bin for temporarily storing deleted lists and cards."""
    
    def __init__(self):
        self._deleted_lists: List[ListObject] = []
        # Store cards as dicts to include metadata like source list and deletion time
        self._deleted_cards: List[Dict[str, Any]] = []
    
    def add_list(self, list_obj: ListObject) -> None:
        """Add a deleted list to the bin."""
        self._deleted_lists.append(list_obj)
    
    def add_card(self, card_obj: Card, source_list_name: str) -> None:
        """Add a deleted card to the bin with its source list information."""
        self._deleted_cards.append({
            "card": card_obj,
            "source_list": source_list_name,
            "deleted_at": datetime.datetime.now().isoformat()
        })
    
    def get_deleted_lists(self) -> List[ListObject]:
        """Get all deleted lists currently in the bin."""
        return self._deleted_lists
    
    def get_deleted_cards(self) -> List[Dict[str, Any]]:
        """Get all deleted cards currently in the bin."""
        return self._deleted_cards
    
    def restore_list(self, list_name: str) -> Optional[ListObject]:
        """Restore a list from the bin by name."""
        list_to_restore = self._find_list_by_name(list_name)
        if list_to_restore:
            self._deleted_lists.remove(list_to_restore)
        return list_to_restore
    
    def restore_card(self, card_name: str, board: 'Board') -> Optional[Dict[str, Any]]:
        """Restore a card from the bin by name, but only if its original list still exists on the board."""
        card_entry = self._find_card_by_name(card_name)
        if card_entry:
            source_list_name = card_entry["source_list"]
            # Check if the source list exists in the board before restoring
            if board._find_list_by_name(source_list_name):
                self._deleted_cards.remove(card_entry)
                return card_entry
        return None
    
    def permanently_delete_list(self, list_name: str) -> bool:
        """Permanently delete a list from the bin."""
        list_to_delete = self._find_list_by_name(list_name)
        if list_to_delete:
            self._deleted_lists.remove(list_to_delete)
            return True
        return False
    
    def permanently_delete_card(self, card_name: str) -> bool:
        """Permanently delete a card from the bin."""
        card_entry = self._find_card_by_name(card_name)
        if card_entry:
            self._deleted_cards.remove(card_entry)
            return True
        return False
    
    def _find_list_by_name(self, list_name: str) -> Optional[ListObject]:
        """Find a list in the bin by its name."""
        return next((lst for lst in self._deleted_lists if lst.name == list_name), None)
    
    def _find_card_by_name(self, card_name: str) -> Optional[Dict[str, Any]]:
        """Find a card entry in the bin by the card's name."""
        return next((entry for entry in self._deleted_cards if entry["card"].name == card_name), None)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert bin object to a dictionary for serialization."""
        return {
            "lists": [lst.to_dict() for lst in self._deleted_lists],
            "cards": [
                {
                    "card": entry["card"].to_dict(),
                    "source_list": entry["source_list"],
                    "deleted_at": entry["deleted_at"]
                }
                for entry in self._deleted_cards
            ]
        }
    
    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> 'Bin':
        """Create a Bin instance from a dictionary."""
        bin_instance = cls()
        if data:
            bin_instance._deleted_lists = [
                ListObject.from_dict(list_data) 
                for list_data in data.get("lists", [])
            ]
            bin_instance._deleted_cards = [
                {
                    "card": Card.from_dict(entry["card"]),
                    "source_list": entry["source_list"],
                    "deleted_at": entry["deleted_at"]
                }
                for entry in data.get("cards", [])
            ]
        return bin_instance


class Board:
    """Represents a board containing multiple lists and a recycle bin."""
    
    def __init__(self, name: str = "Default Board", lists: Optional[List[Dict[str, Any]]] = None, bin_data: Optional[Dict[str, Any]] = None, completed_list_name: Optional[str] = None):
        self.name = name
        self.completed_list_name = completed_list_name
        self._list_objects = [ListObject.from_dict(list_data) for list_data in lists] if lists else []
        self.bin = Bin.from_dict(bin_data)
    
    def list_objects(self) -> List[ListObject]:
        """Get all list objects in this board."""
        return self._list_objects
    
    def create_list(self, name: str, description: str = "") -> Optional[ListObject]:
        """Create a new list if the name is valid and doesn't already exist."""
        if not name:
            return None
            
        # Prevent creating lists with duplicate names (case-insensitive check)
        if any(lst.name.lower() == name.lower() for lst in self._list_objects):
            return None
            
        new_list = ListObject(name=name, description=description)
        self._list_objects.append(new_list)
        return new_list
    
    def delete_list(self, list_name: str) -> bool:
        """Delete a list by moving it to the bin."""
        list_to_delete = self._find_list_by_name(list_name)
        if list_to_delete:
            # If the deleted list was the 'completed' list, unset it
            if self.completed_list_name == list_name:
                self.completed_list_name = None
            self._list_objects.remove(list_to_delete)
            self.bin.add_list(list_to_delete)
            return True
        return False
    
    def delete_card(self, list_name: str, card_to_delete: Card) -> bool:
        """Finds a list, moves a card to the bin, and then deletes it from the list."""
        list_obj = self._find_list_by_name(list_name)
        if not list_obj:
            return False

        # First, add the card to the bin with its source list name
        self.bin.add_card(card_to_delete, source_list_name=list_name)
        # Then, remove the card from the list
        return list_obj.delete_card(card_to_delete)

    def set_completed_list(self, list_name: Optional[str]):
        """Set or unset a list as the designated 'completed' list."""
        # Ensure the list exists before setting it as the completed list
        if list_name and not self._find_list_by_name(list_name):
            return False
        self.completed_list_name = list_name
        return True

    def get_completed_list_name(self) -> Optional[str]:
        """Get the name of the 'completed' list."""
        return self.completed_list_name

    def move_card(self, card_to_move: Card, source_list_name: str, dest_list_name: str) -> bool:
        """Move a card from a source list to a destination list."""
        source_list = self._find_list_by_name(source_list_name)
        dest_list = self._find_list_by_name(dest_list_name)

        # Ensure both lists exist and are not the same
        if not source_list or not dest_list or source_list_name == dest_list_name:
            return False

        # Atomically remove from source and add to destination
        if source_list.delete_card(card_to_move):
            dest_list.add_card(card_to_move)
            return True
        return False
    
    def add_list(self, list_obj: ListObject) -> None:
        """Add a list object to this board (e.g., when restoring from bin)."""
        self._list_objects.append(list_obj)
    
    def rename_board(self, new_name: str) -> bool:
        """Rename this board. Returns True if successful."""
        if new_name:
            self.name = new_name
            return True
        return False
    
    def _find_list_by_name(self, list_name: str) -> Optional[ListObject]:
        """Find a list in this board by its name."""
        return next((lst for lst in self._list_objects if lst.name == list_name), None)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert board object to a dictionary for serialization."""
        return {
            "name": self.name,
            "lists": [lst.to_dict() for lst in self._list_objects],
            "bin": self.bin.to_dict(),
            "completed_list_name": self.completed_list_name
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Board':
        """Create a Board instance from a dictionary."""
        return cls(
            name=data.get("name", "Default Board"),
            lists=data.get("lists", []),
            bin_data=data.get("bin"),
            completed_list_name=data.get("completed_list_name")
        )


class Workspace:
    """Represents a workspace, which is a container for multiple boards and is saved as a single file."""
    
    def __init__(self, name: str, password: Optional[str] = None, path: Optional[str] = None):
        self.name = name
        self.path = path  # Filesystem path to the workspace directory
        self._password = password  # In-memory password for the current session
        self.last_edited = datetime.datetime.now().astimezone()
        # A new workspace starts with one default board
        self._boards = [Board(name="New Board")]
        self._selected_board_index = 0
    
    def selected_board(self) -> Optional[Board]:
        """Get the currently selected board."""
        if 0 <= self._selected_board_index < len(self._boards):
            return self._boards[self._selected_board_index]
        return None
    
    def set_selected_board_by_index(self, index: int) -> bool:
        """Set the selected board by its index. Returns True if successful."""
        if 0 <= index < len(self._boards):
            self._selected_board_index = index
            return True
        return False
    
    def create_board(self) -> Board:
        """Create a new board in this workspace."""
        new_board = Board(name=f"Board {len(self._boards) + 1}")
        self._boards.append(new_board)
        self.update_last_edited()
        return new_board
    
    def set_password(self, new_password: Optional[str]) -> None:
        """Set or clear the workspace password for the current session."""
        self._password = new_password.strip() if new_password else None
    
    def has_password(self) -> bool:
        """Check if this workspace has a password set for the current session."""
        return self._password is not None
    
    def update_last_edited(self) -> None:
        """Update the last edited timestamp to the current time."""
        self.last_edited = datetime.datetime.now().astimezone()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert workspace object to a dictionary for serialization."""
        return {
            "name": self.name,
            "last_edited": self.last_edited.isoformat(),
            "boards": [board.to_dict() for board in self._boards],
            "selected_board_index": self._selected_board_index
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], path: str) -> 'Workspace':
        """Create a Workspace instance from a dictionary."""
        workspace = cls(name=data.get("name", "Unnamed"), path=path)
        
        # Safely parse the last_edited timestamp
        if last_edited_str := data.get("last_edited"):
            try:
                workspace.last_edited = datetime.datetime.fromisoformat(last_edited_str)
            except ValueError:
                # Fallback if the timestamp is malformed
                workspace.last_edited = datetime.datetime.now(datetime.timezone.utc)
        
        # Load boards from data
        if boards_data := data.get("boards"):
            workspace._boards = [Board.from_dict(board_data) for board_data in boards_data]
        
        # Ensure at least one board always exists
        if not workspace._boards:
            workspace._boards = [Board(name="New Board")]
        
        # Validate and set the selected board index
        workspace._selected_board_index = data.get("selected_board_index", 0)
        if workspace._selected_board_index >= len(workspace._boards):
            workspace._selected_board_index = 0
        
        return workspace


class WorkspaceManager:
    """Manages all workspaces, handling creation, loading, saving, and deletion from the filesystem."""
    
    def __init__(self, config_path: str = "workspaces.json", workspaces_dir: str = "workspaces"):
        self.workspaces_dir = workspaces_dir  # Directory to store all workspace folders
        self.config_path = config_path  # Master JSON file tracking all workspaces
        self._workspaces_registry: Dict[str, Dict[str, Any]] = {}
        self._current_workspace: Optional[Workspace] = None
        self._initialize()
    
    def _initialize(self) -> None:
        """Initialize the manager by creating necessary directories and loading the master config."""
        os.makedirs(self.workspaces_dir, exist_ok=True)
        self._load_master_config()
    
    def _load_master_config(self) -> None:
        """Load the master configuration file that contains the workspace registry."""
        if not os.path.exists(self.config_path):
            self._workspaces_registry = {}
            return
        
        try:
            with open(self.config_path, "r") as file:
                self._workspaces_registry = json.load(file)
            # Clean up any entries that point to non-existent or invalid workspaces
            self._clean_invalid_workspaces()
        except (IOError, json.JSONDecodeError):
            # If the config is corrupted or unreadable, start with an empty registry
            self._workspaces_registry = {}
    
    def _save_master_config(self) -> None:
        """Save the current workspace registry to the master configuration file."""
        try:
            with open(self.config_path, "w") as file:
                json.dump(self._workspaces_registry, file, indent=2)
        except IOError as e:
            print(f"Error saving master config: {e}")
    
    def _clean_invalid_workspaces(self) -> None:
        """Remove entries from the registry if their corresponding workspace directory or data file is missing."""
        valid_workspaces = {
            name: data for name, data in self._workspaces_registry.items() 
            if self._is_valid_workspace_entry(data)
        }
        
        if len(valid_workspaces) != len(self._workspaces_registry):
            self._workspaces_registry = valid_workspaces
            self._save_master_config()
    
    def _is_valid_workspace_entry(self, data: Any) -> bool:
        """Check if a workspace registry entry is valid by verifying its path and data file."""
        if not isinstance(data, dict):
            return False
        
        path = data.get("path")
        if not path or not os.path.isdir(path):
            return False
        
        # A valid workspace must have a data.json file inside its directory
        return os.path.exists(os.path.join(path, "data.json"))
    
    def _is_file_encrypted(self, file_path: str) -> bool:
        """Check if a file is encrypted by attempting to parse it as JSON.
        Assumes unencrypted files are valid UTF-8 encoded JSON."""
        try:
            with open(file_path, 'rb') as file:
                # If it can be decoded and loaded as JSON, it's not encrypted
                json.loads(file.read().decode('utf-8'))
            return False
        except (UnicodeDecodeError, json.JSONDecodeError, IOError):
            # Any of these errors suggest the file is binary/encrypted or unreadable
            return True
    
    def current_workspace(self) -> Optional[Workspace]:
        """Get the currently open workspace."""
        return self._current_workspace
    
    def create_workspace(self, name: str) -> Optional[Workspace]:
        """Create a new workspace directory and its initial data file."""
        if not name or name in self._workspaces_registry:
            return None
        
        workspace_path = os.path.join(self.workspaces_dir, name)
        if os.path.exists(workspace_path):
            return None
        
        try:
            os.makedirs(workspace_path)
            workspace = Workspace(name, path=workspace_path)
            self._current_workspace = workspace
            
            self._workspaces_registry[name] = {
                "path": workspace_path,
                "last_edited": workspace.last_edited.isoformat()
            }
            
            self.save_current_workspace()
            # Close workspace immediately after creation to ensure consistent state management
            self.close_current_workspace()
            return workspace
        except OSError:
            return None
    
    def open_workspace(self, name: str, password: Optional[str] = None) -> Union[Workspace, str, None]:
        """
        Open a workspace by name.
        Returns:
            - Workspace object: on successful opening.
            - "password_required": if the workspace is encrypted and no password was provided.
            - None: if the workspace doesn't exist or an error occurs (e.g., wrong password).
        """
        if self._current_workspace or name not in self._workspaces_registry:
            return None
        
        path = self._workspaces_registry[name]["path"]
        data_path = os.path.join(path, "data.json")
        
        try:
            is_encrypted = self._is_file_encrypted(data_path)
            if is_encrypted and not password:
                return "password_required"
            
            with open(data_path, "rb") as file:
                content = file.read()
            
            if is_encrypted:
                # Decrypt with the provided password
                data_str = EncryptionHelper.decrypt(content, password)
            else:
                data_str = content.decode('utf-8')
            
            workspace_data_dict = json.loads(data_str)
            workspace = Workspace.from_dict(workspace_data_dict, path)
            workspace._password = password  # Store password for the session
            
            self._current_workspace = workspace
            return workspace
        except (InvalidToken, IOError, json.JSONDecodeError, ValueError):
            # InvalidToken means wrong password. Other errors handle file/data corruption.
            return None
    
    def save_current_workspace(self) -> bool:
        """Save the currently open workspace to disk, encrypting if a password is set."""
        if not self._current_workspace:
            return False
        
        workspace = self._current_workspace
        workspace.update_last_edited()
        
        data_path = os.path.join(workspace.path, "data.json")
        json_data = json.dumps(workspace.to_dict(), indent=2)
        
        try:
            if workspace.has_password():
                # Encrypt data before writing to file
                encrypted_data = EncryptionHelper.encrypt(json_data, workspace._password)
                with open(data_path, "wb") as file:
                    file.write(encrypted_data)
            else:
                # Write plaintext JSON to file
                with open(data_path, "w", encoding='utf-8') as file:
                    file.write(json_data)
            
            # Update the last_edited timestamp in the master config
            if workspace.name in self._workspaces_registry:
                self._workspaces_registry[workspace.name]["last_edited"] = workspace.last_edited.isoformat()
                self._save_master_config()
            
            return True
        except IOError:
            return False
    
    def close_current_workspace(self) -> None:
        """Close the currently open workspace, clearing it from memory."""
        self._current_workspace = None
    
    def workspaces(self) -> Dict[str, Dict[str, Any]]:
        """Get the registry of all known workspaces."""
        return self._workspaces_registry
    
    def is_workspace_encrypted(self, name: str) -> bool:
        """Check if a workspace's data file is encrypted without opening it."""
        if name not in self._workspaces_registry:
            return False
        
        data_path = os.path.join(self._workspaces_registry[name]["path"], "data.json")
        return self._is_file_encrypted(data_path)
    
    def delete_workspace(self, name: str) -> bool:
        """Permanently delete a workspace's directory and remove it from the registry."""
        if name not in self._workspaces_registry:
            return False
        
        # Safety check: do not delete the currently open workspace
        if self._current_workspace and self._current_workspace.name == name:
            return False
        
        try:
            # Remove the entire workspace directory
            shutil.rmtree(self._workspaces_registry[name]["path"])
            # Remove from registry and save the change
            del self._workspaces_registry[name]
            self._save_master_config()
            return True
        except OSError:
            return False
    
    def rename_workspace(self, old_name: str, new_name: str, password: Optional[str] = None) -> bool:
        """Rename a workspace, which involves renaming its directory and updating the registry."""
        if not new_name or new_name in self._workspaces_registry or old_name not in self._workspaces_registry:
            return False
        
        # To rename, we must first open the workspace to update its internal name property
        workspace = self.open_workspace(old_name, password=password)
        if not isinstance(workspace, Workspace):
            # Handle password errors or other opening failures
            if self._current_workspace: self.close_current_workspace()
            return False
        
        old_path = workspace.path
        new_path = os.path.join(self.workspaces_dir, new_name)
        
        try:
            # 1. Update workspace name in memory and save it to the data file
            workspace.name = new_name
            self._current_workspace = workspace
            self.save_current_workspace()
            self.close_current_workspace()
            
            # 2. Rename the workspace directory
            os.rename(old_path, new_path)
            
            # 3. Update the registry with the new name and path
            registry_entry = self._workspaces_registry.pop(old_name)
            registry_entry["path"] = new_path
            self._workspaces_registry[new_name] = registry_entry
            self._save_master_config()
            
            return True
        except Exception as e:
            print(f"An error occurred during rename: {e}")
            # Attempt to roll back the directory rename if it happened before another error
            if not os.path.exists(old_path) and os.path.exists(new_path):
                os.rename(new_path, old_path)
            return False