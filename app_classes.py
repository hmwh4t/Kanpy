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
    
    SALT_LENGTH = 16
    KEY_LENGTH = 32
    ITERATIONS = 100000
    
    @staticmethod
    def derive_key(password: str, salt: bytes) -> bytes:
        """Derive an encryption key from a password and salt."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=EncryptionHelper.KEY_LENGTH,
            salt=salt,
            iterations=EncryptionHelper.ITERATIONS,
            backend=default_backend()
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))
    
    @staticmethod
    def encrypt(data_str: str, password: str) -> bytes:
        """Encrypt a string using a password."""
        salt = os.urandom(EncryptionHelper.SALT_LENGTH)
        key = EncryptionHelper.derive_key(password, salt)
        encrypted_data = Fernet(key).encrypt(data_str.encode('utf-8'))
        return salt + encrypted_data
    
    @staticmethod
    def decrypt(encrypted_data: bytes, password: str) -> str:
        """Decrypt encrypted data using a password."""
        salt = encrypted_data[:EncryptionHelper.SALT_LENGTH]
        ciphertext = encrypted_data[EncryptionHelper.SALT_LENGTH:]
        key = EncryptionHelper.derive_key(password, salt)
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
            deadline_date = datetime.datetime.strptime(self.deadline, '%Y-%m-%d %H:%M').date()
            return deadline_date < datetime.date.today()
        except (ValueError, TypeError):
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert card to dictionary representation."""
        return self.__dict__
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Card':
        """Create a Card instance from dictionary data."""
        card = cls(
            name=data.get("name", "Untitled"),
            description=data.get("description", ""),
            deadline=data.get("deadline"),
            priority=data.get("priority", 0)
        )
        card.completed = data.get("completed", False)
        return card
    
    def get_priority_display(self) -> str:
        """Return a string of red exclamation marks based on priority."""
        return "[color=ff0000]" + "❗" * self.priority + "[/color]"


class ListObject:
    """Represents a list containing multiple cards."""
    
    def __init__(self, name: str = "Untitled List", description: str = "", cards: Optional[List[Dict[str, Any]]] = None):
        self.name = name
        self.description = description
        
        if cards:
            self._cards = [Card.from_dict(card_data) for card_data in cards]
        else:
            self._cards = []
    
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
            # Card was not found in the list
            return False
    
    def _find_card_by_name(self, card_name: str) -> Optional[Card]:
        """Find a card in this list by name."""
        return next((card for card in self._cards if card.name == card_name), None)

    def rename_list(self, new_name: str) -> bool:
        """Rename this list. Returns True if successful."""
        if new_name:
            self.name = new_name
            return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert list to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "cards": [card.to_dict() for card in self._cards]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ListObject':
        """Create a ListObject instance from dictionary data."""
        return cls(
            name=data.get("name", "Untitled List"),
            description=data.get("description", ""),
            cards=data.get("cards", [])
        )


class Bin:
    """Represents a recycle bin for deleted lists and cards."""
    
    def __init__(self):
        self._deleted_lists: List[ListObject] = []
        self._deleted_cards: List[Dict[str, Any]] = []  # Store card with source list info
    
    def add_list(self, list_obj: ListObject) -> None:
        """Add a deleted list to the bin."""
        self._deleted_lists.append(list_obj)
    
    def add_card(self, card_obj: Card, source_list_name: str) -> None:
        """Add a deleted card to the bin with source list information."""
        self._deleted_cards.append({
            "card": card_obj,
            "source_list": source_list_name,
            "deleted_at": datetime.datetime.now().isoformat()
        })
    
    def get_deleted_lists(self) -> List[ListObject]:
        """Get all deleted lists in the bin."""
        return self._deleted_lists
    
    def get_deleted_cards(self) -> List[Dict[str, Any]]:
        """Get all deleted cards in the bin."""
        return self._deleted_cards
    
    def restore_list(self, list_name: str) -> Optional[ListObject]:
        """Restore a list from the bin by name."""
        list_to_restore = self._find_list_by_name(list_name)
        if list_to_restore:
            self._deleted_lists.remove(list_to_restore)
        return list_to_restore
    
    def restore_card(self, card_name: str, board: 'Board') -> Optional[Dict[str, Any]]:
        """Restore a card from the bin by name, only if the source list exists."""
        card_entry = self._find_card_by_name(card_name)
        if card_entry:
            source_list_name = card_entry["source_list"]
            # Check if the source list exists in the board
            source_list = board._find_list_by_name(source_list_name)
            if source_list:
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
        """Find a list in the bin by name."""
        return next((lst for lst in self._deleted_lists if lst.name == list_name), None)
    
    def _find_card_by_name(self, card_name: str) -> Optional[Dict[str, Any]]:
        """Find a card in the bin by name."""
        return next((entry for entry in self._deleted_cards if entry["card"].name == card_name), None)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert bin to dictionary representation."""
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
        """Create a Bin instance from dictionary data."""
        bin_instance = cls()
        if data:
            if "lists" in data:
                bin_instance._deleted_lists = [
                    ListObject.from_dict(list_data) 
                    for list_data in data.get("lists", [])
                ]
            if "cards" in data:
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
        
        if lists:
            self._list_objects = [ListObject.from_dict(list_data) for list_data in lists]
        else:
            self._list_objects = []
            
        self.bin = Bin.from_dict(bin_data)
    
    def list_objects(self) -> List[ListObject]:
        """Get all list objects in this board."""
        return self._list_objects
    
    def create_list(self, name: str, description: str = "") -> Optional[ListObject]:
        """Create a new list if the name doesn't already exist."""
        if not name:
            return None
            
        # Check if list name already exists (case-insensitive)
        if any(lst.name.lower() == name.lower() for lst in self._list_objects):
            return None
            
        new_list = ListObject(name=name, description=description)
        self._list_objects.append(new_list)
        return new_list
    
    def delete_list(self, list_name: str) -> bool:
        """Delete a list by moving it to the bin."""
        list_to_delete = self._find_list_by_name(list_name)
        if list_to_delete:
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

        self.bin.add_card(card_to_delete, source_list_name=list_name)
        return list_obj.delete_card(card_to_delete)

    def set_completed_list(self, list_name: Optional[str]):
        """Set or unset a list as the completed list."""
        if list_name and not self._find_list_by_name(list_name):
            return False # List doesn't exist
        self.completed_list_name = list_name
        return True

    def get_completed_list_name(self) -> Optional[str]:
        """Get the name of the completed list."""
        return self.completed_list_name

    def move_card(self, card_to_move: Card, source_list_name: str, dest_list_name: str) -> bool:
        """Move a card from a source list to a destination list."""
        source_list = self._find_list_by_name(source_list_name)
        dest_list = self._find_list_by_name(dest_list_name)

        if not source_list or not dest_list or source_list_name == dest_list_name:
            return False

        if source_list.delete_card(card_to_move):
            dest_list.add_card(card_to_move)
            return True
        return False
    
    def add_list(self, list_obj: ListObject) -> None:
        """Add a list object to this board."""
        self._list_objects.append(list_obj)
    
    def rename_board(self, new_name: str) -> bool:
        """Rename this board. Returns True if successful."""
        if new_name:
            self.name = new_name
            return True
        return False
    
    def _find_list_by_name(self, list_name: str) -> Optional[ListObject]:
        """Find a list in this board by name."""
        return next((lst for lst in self._list_objects if lst.name == list_name), None)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert board to dictionary representation."""
        return {
            "name": self.name,
            "lists": [lst.to_dict() for lst in self._list_objects],
            "bin": self.bin.to_dict(),
            "completed_list_name": self.completed_list_name
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Board':
        """Create a Board instance from dictionary data."""
        return cls(
            name=data.get("name", "Default Board"),
            lists=data.get("lists", []),
            bin_data=data.get("bin"),
            completed_list_name=data.get("completed_list_name")
        )


class Workspace:
    """Represents a workspace containing multiple boards."""
    
    def __init__(self, name: str, password: Optional[str] = None, path: Optional[str] = None):
        self.name = name
        self.path = path
        self._password = password
        self.last_edited = datetime.datetime.now().astimezone()
        self._boards = [Board(name="New Board")]
        self._selected_board_index = 0
    
    def selected_board(self) -> Optional[Board]:
        """Get the currently selected board."""
        if 0 <= self._selected_board_index < len(self._boards):
            return self._boards[self._selected_board_index]
        return None
    
    def set_selected_board_by_index(self, index: int) -> bool:
        """Set the selected board by index. Returns True if successful."""
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
        """Set or clear the workspace password."""
        self._password = new_password.strip() if new_password else None
    
    def has_password(self) -> bool:
        """Check if this workspace has a password set."""
        return self._password is not None
    
    def update_last_edited(self) -> None:
        """Update the last edited timestamp to now."""
        self.last_edited = datetime.datetime.now().astimezone()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert workspace to dictionary representation."""
        return {
            "name": self.name,
            "last_edited": self.last_edited.isoformat(),
            "boards": [board.to_dict() for board in self._boards],
            "selected_board_index": self._selected_board_index
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], path: str) -> 'Workspace':
        """Create a Workspace instance from dictionary data."""
        workspace = cls(name=data.get("name", "Unnamed"), path=path)
        
        # Parse last_edited timestamp
        if last_edited_str := data.get("last_edited"):
            try:
                workspace.last_edited = datetime.datetime.fromisoformat(last_edited_str)
            except ValueError:
                workspace.last_edited = datetime.datetime.now(datetime.timezone.utc)
        
        # Load boards
        if boards_data := data.get("boards"):
            workspace._boards = [Board.from_dict(board_data) for board_data in boards_data]
        
        # Ensure at least one board exists
        if not workspace._boards:
            workspace._boards = [Board(name="New Board")]
        
        # Set selected board index
        workspace._selected_board_index = data.get("selected_board_index", 0)
        if workspace._selected_board_index >= len(workspace._boards):
            workspace._selected_board_index = 0
        
        return workspace


class WorkspaceManager:
    """Manages multiple workspaces, including creation, loading, saving, and deletion."""
    
    def __init__(self, config_path: str = "workspaces.json", workspaces_dir: str = "workspaces"):
        self.workspaces_dir = workspaces_dir
        self.config_path = config_path
        self._workspaces_registry: Dict[str, Dict[str, Any]] = {}
        self._current_workspace: Optional[Workspace] = None
        self._initialize()
    
    def _initialize(self) -> None:
        """Initialize the workspace manager by creating directories and loading config."""
        os.makedirs(self.workspaces_dir, exist_ok=True)
        self._load_master_config()
    
    def _load_master_config(self) -> None:
        """Load the master configuration file containing workspace registry."""
        if not os.path.exists(self.config_path):
            self._workspaces_registry = {}
            return
        
        try:
            with open(self.config_path, "r") as file:
                self._workspaces_registry = json.load(file)
            self._clean_invalid_workspaces()
        except (IOError, json.JSONDecodeError):
            self._workspaces_registry = {}
    
    def _save_master_config(self) -> None:
        """Save the master configuration file."""
        try:
            with open(self.config_path, "w") as file:
                json.dump(self._workspaces_registry, file, indent=2)
        except IOError as e:
            print(f"Error saving master config: {e}")
    
    def _clean_invalid_workspaces(self) -> None:
        """Remove invalid workspace entries from the registry."""
        valid_workspaces = {}
        
        for name, data in self._workspaces_registry.items():
            if self._is_valid_workspace_entry(data):
                valid_workspaces[name] = data
        
        if len(valid_workspaces) != len(self._workspaces_registry):
            self._workspaces_registry = valid_workspaces
            self._save_master_config()
    
    def _is_valid_workspace_entry(self, data: Any) -> bool:
        """Check if a workspace registry entry is valid."""
        if not isinstance(data, dict):
            return False
        
        path = data.get("path")
        if not path or not os.path.isdir(path):
            return False
        
        data_file_path = os.path.join(path, "data.json")
        return os.path.exists(data_file_path)
    
    def _is_file_encrypted(self, file_path: str) -> bool:
        """Check if a file is encrypted by trying to parse it as JSON."""
        try:
            with open(file_path, 'rb') as file:
                json.loads(file.read().decode('utf-8'))
            return False
        except (UnicodeDecodeError, json.JSONDecodeError, IOError):
            return True
    
    def current_workspace(self) -> Optional[Workspace]:
        """Get the currently open workspace."""
        return self._current_workspace
    
    def create_workspace(self, name: str) -> Optional[Workspace]:
        """Create a new workspace with the given name."""
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
            self.close_current_workspace()  # FIX: This line prevents the state management bug
            return workspace
        except OSError:
            return None
    
    def open_workspace(self, name: str, password: Optional[str] = None) -> Union[Workspace, str, None]:
        """
        Open a workspace by name.
        Returns:
            - Workspace object if successful
            - "password_required" if password is needed but not provided
            - None if failed to open
        """
        if self._current_workspace or name not in self._workspaces_registry:
            return None
        
        workspace_data = self._workspaces_registry[name]
        path = workspace_data["path"]
        data_path = os.path.join(path, "data.json")
        
        try:
            if self._is_file_encrypted(data_path) and not password:
                return "password_required"
            
            with open(data_path, "rb") as file:
                content = file.read()
            
            if self._is_file_encrypted(data_path):
                data_str = EncryptionHelper.decrypt(content, password)
            else:
                data_str = content.decode('utf-8')
            
            workspace_data_dict = json.loads(data_str)
            workspace = Workspace.from_dict(workspace_data_dict, path)
            workspace._password = password
            
            self._current_workspace = workspace
            return workspace
        except (InvalidToken, IOError, json.JSONDecodeError, ValueError):
            return None
    
    def save_current_workspace(self) -> bool:
        """Save the currently open workspace to disk."""
        if not self._current_workspace:
            return False
        
        workspace = self._current_workspace
        workspace.update_last_edited()
        
        data_path = os.path.join(workspace.path, "data.json")
        json_data = json.dumps(workspace.to_dict(), indent=2)
        
        try:
            if workspace.has_password():
                encrypted_data = EncryptionHelper.encrypt(json_data, workspace._password)
                with open(data_path, "wb") as file:
                    file.write(encrypted_data)
            else:
                with open(data_path, "w", encoding='utf-8') as file:
                    file.write(json_data)
            
            # Update registry
            if workspace.name in self._workspaces_registry:
                self._workspaces_registry[workspace.name]["last_edited"] = workspace.last_edited.isoformat()
                self._save_master_config()
            
            return True
        except IOError:
            return False
    
    def close_current_workspace(self) -> None:
        """Close the currently open workspace."""
        self._current_workspace = None
    
    def workspaces(self) -> Dict[str, Dict[str, Any]]:
        """Get the registry of all workspaces."""
        return self._workspaces_registry
    
    def is_workspace_encrypted(self, name: str) -> bool:
        """Check if a workspace is encrypted."""
        if name not in self._workspaces_registry:
            return False
        
        data_path = os.path.join(self._workspaces_registry[name]["path"], "data.json")
        return self._is_file_encrypted(data_path)
    
    def delete_workspace(self, name: str) -> bool:
        """Delete a workspace completely."""
        if name not in self._workspaces_registry:
            return False
        
        # Don't delete currently open workspace
        if self._current_workspace and self._current_workspace.name == name:
            return False
        
        try:
            shutil.rmtree(self._workspaces_registry[name]["path"])
            del self._workspaces_registry[name]
            self._save_master_config()
            return True
        except OSError:
            return False
    
    def rename_workspace(self, old_name: str, new_name: str, password: Optional[str] = None) -> bool:
        """Rename a workspace."""
        if not new_name or new_name in self._workspaces_registry or old_name not in self._workspaces_registry:
            return False
        
        workspace = self.open_workspace(old_name, password=password)
        if not workspace or workspace == "password_required":
            if self._current_workspace:
                self.close_current_workspace()
            return False
        
        old_path = workspace.path
        new_path = os.path.join(self.workspaces_dir, new_name)
        
        try:
            # Update workspace name and save
            workspace.name = new_name
            self._current_workspace = workspace
            self.save_current_workspace()
            self.close_current_workspace()
            
            # Rename directory
            os.rename(old_path, new_path)
            
            # Update registry
            registry_entry = self._workspaces_registry.pop(old_name)
            registry_entry["path"] = new_path
            self._workspaces_registry[new_name] = registry_entry
            self._save_master_config()
            
            return True
        except Exception as e:
            print(f"An error occurred during rename: {e}")
            # Attempt to rollback directory rename if it happened
            if not os.path.exists(old_path) and os.path.exists(new_path):
                os.rename(new_path, old_path)
            return False