import datetime
import traceback
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import ObjectProperty, StringProperty, BooleanProperty
from kivy.clock import Clock
from kivy.uix.modalview import ModalView
from kivy.metrics import dp
from kivy.utils import get_color_from_hex
from kivy.graphics import Color, Rectangle
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior
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
    """Represents a recycle bin for deleted lists."""
    
    def __init__(self):
        self._deleted_lists: List[ListObject] = []
    
    def add_list(self, list_obj: ListObject) -> None:
        """Add a deleted list to the bin."""
        self._deleted_lists.append(list_obj)
    
    def get_deleted_lists(self) -> List[ListObject]:
        """Get all deleted lists in the bin."""
        return self._deleted_lists
    
    def restore_list(self, list_name: str) -> Optional[ListObject]:
        """Restore a list from the bin by name."""
        list_to_restore = self._find_list_by_name(list_name)
        if list_to_restore:
            self._deleted_lists.remove(list_to_restore)
        return list_to_restore
    
    def permanently_delete_list(self, list_name: str) -> bool:
        """Permanently delete a list from the bin."""
        list_to_delete = self._find_list_by_name(list_name)
        if list_to_delete:
            self._deleted_lists.remove(list_to_delete)
            return True
        return False
    
    def _find_list_by_name(self, list_name: str) -> Optional[ListObject]:
        """Find a list in the bin by name."""
        return next((lst for lst in self._deleted_lists if lst.name == list_name), None)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert bin to dictionary representation."""
        return {
            "lists": [lst.to_dict() for lst in self._deleted_lists]
        }
    
    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> 'Bin':
        """Create a Bin instance from dictionary data."""
        bin_instance = cls()
        if data and "lists" in data:
            bin_instance._deleted_lists = [
                ListObject.from_dict(list_data) 
                for list_data in data.get("lists", [])
            ]
        return bin_instance


class Board:
    """Represents a board containing multiple lists and a recycle bin."""
    
    def __init__(self, name: str = "Default Board", lists: Optional[List[Dict[str, Any]]] = None, bin_data: Optional[Dict[str, Any]] = None):
        self.name = name
        
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
            self._list_objects.remove(list_to_delete)
            self.bin.add_list(list_to_delete)
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
            "bin": self.bin.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Board':
        """Create a Board instance from dictionary data."""
        return cls(
            name=data.get("name", "Default Board"),
            lists=data.get("lists", []),
            bin_data=data.get("bin")
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

APP_COLORS = {
    "background": get_color_from_hex("#FAFAFA"),
    "background_dark": get_color_from_hex("#D1D5DB"),
    "primary": get_color_from_hex("#2563EB"),
    "primary_dark": get_color_from_hex("#1D4ED8"),
    "accent": get_color_from_hex("#10B981"),
    "text": get_color_from_hex("#1F2937"),
    "text_secondary": get_color_from_hex("#6B7280"),
    "white": get_color_from_hex("#FFFFFF"),
    "red": get_color_from_hex("#EF4444"),
    "border": get_color_from_hex("#E5E7EB"),
    "card": get_color_from_hex("#FFFFFF"),
    "hover": get_color_from_hex("#F3F4F6")
}

class Toast(ModalView):
    text = StringProperty('')

    def __init__(self, text, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        Clock.schedule_once(self.dismiss, 1.5)

class TextInputPopup(ModalView):
    title = StringProperty("Enter Value")
    hint_text = StringProperty("")
    callback = ObjectProperty(None)
    is_password = BooleanProperty(False)

    def on_submit(self, text_input):
        if self.callback:
            self.callback(text_input)
        self.dismiss()

class WorkspaceOptionsDialog(ModalView):
    workspace_name = StringProperty("")
    is_encrypted = BooleanProperty(False)

    def __init__(self, workspace_name, **kwargs):
        super().__init__(**kwargs)
        self.workspace_name = workspace_name
        self.is_encrypted = App.get_running_app().workspace_manager.is_workspace_encrypted(self.workspace_name)

class BoardOptionsDialog(ModalView):
    board_screen = ObjectProperty(None)

    def open_bin(self):
        self.dismiss()
        self.board_screen.manager.current = 'bin_screen'

    def delete_board(self):
        self.dismiss()
        workspace = App.get_running_app().workspace_manager.current_workspace()
        if not workspace or len(workspace._boards) <= 1:
            App.get_running_app().show_toast("Cannot delete the last board")
            return

        current_board = workspace.selected_board()
        if current_board:
            workspace._boards.remove(current_board)
            if workspace._selected_board_index >= len(workspace._boards):
                workspace._selected_board_index = len(workspace._boards) - 1

            App.get_running_app().workspace_manager.save_current_workspace()
            App.get_running_app().show_toast(f"Board '{current_board.name}' deleted")
            self.board_screen.load_current_board()

class ListContextMenu(ModalView):
    list_widget = ObjectProperty(None)

    def __init__(self, list_widget, **kwargs):
        super().__init__(**kwargs)
        self.list_widget = list_widget

    def rename(self):
        self.dismiss()
        self.list_widget.rename_popup()

    def move_to_bin(self):
        self.dismiss()
        self.list_widget.move_to_bin()

class CreateBoardDialog(ModalView):
    board_screen = ObjectProperty(None)

    def create_new_board(self):
        self.dismiss()
        self.board_screen.create_new_board_and_load_it()

# --- MODIFIED: REMOVED ALL TOUCH HANDLING ---
# This widget no longer needs custom touch handling, as buttons will be used for interaction.
class ClickableHeader(BoxLayout):
    board_screen = ObjectProperty(None)

# --- MODIFIED: REMOVED ALL TOUCH HANDLING ---
class ListHeader(BoxLayout): # Removed ButtonBehavior
    list_widget = ObjectProperty(None)

class WorkspaceCard(ButtonBehavior, BoxLayout):
    workspace_name = StringProperty('')
    app = ObjectProperty(None)
    last_edited_date = StringProperty('')
    last_edited_time = StringProperty('')
    _long_press_event = None

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.cancel_long_press_event()
            self._long_press_event = Clock.schedule_once(self.long_press_callback, 0.5)
            # We still return super() to allow ButtonBehavior to work for visual feedback
            return super().on_touch_down(touch)
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            # If a long press was scheduled, cancel it and trigger a short press
            if self._long_press_event:
                self.cancel_long_press_event()
                self.short_press_callback()
                return True # Event handled
        # If the touch is released outside or long press already happened
        self.cancel_long_press_event()
        return super().on_touch_up(touch)

    def cancel_long_press_event(self):
        if self._long_press_event:
            self._long_press_event.cancel()
            self._long_press_event = None

    def short_press_callback(self):
        self.app.open_workspace(self.workspace_name)

    def long_press_callback(self, _dt):
        self._long_press_event = None
        WorkspaceOptionsDialog(workspace_name=self.workspace_name).open()


class ListWidget(BoxLayout):
    list_name = StringProperty('')
    board_widget = ObjectProperty(None)

    # The context menu is now opened only by the dedicated button in the kv file
    def open_context_menu(self):
        menu = ListContextMenu(list_widget=self)
        menu.open()

    def rename_popup(self):
        TextInputPopup(
            title="Rename List",
            hint_text=self.list_name,
            callback=self.rename_callback
        ).open()

    def rename_callback(self, new_name):
        if not new_name:
            return

        list_obj = next((l for l in self.board_widget.board.list_objects() if l.name == self.list_name), None)
        if list_obj and list_obj.rename_list(new_name):
            App.get_running_app().workspace_manager.save_current_workspace()
            self.board_widget.populate_lists()
            App.get_running_app().show_toast(f"List renamed to '{new_name}'")

    def move_to_bin(self):
        if self.board_widget.board.delete_list(self.list_name):
            App.get_running_app().workspace_manager.save_current_workspace()
            self.board_widget.populate_lists()
            App.get_running_app().show_toast(f"'{self.list_name}' moved to bin")


class BoardWidget(RelativeLayout):
    board = ObjectProperty(None)

    def __init__(self, board, **kwargs):
        super().__init__(**kwargs)
        self.board = board
        Clock.schedule_once(lambda dt: self.populate_lists())

    def populate_lists(self):
        lists_container = self.ids.lists_container
        lists_container.clear_widgets()

        if not self.board.list_objects():
            self.ids.empty_board_label.opacity = 1
            self.ids.scroll_view.opacity = 0
        else:
            self.ids.empty_board_label.opacity = 0
            self.ids.scroll_view.opacity = 1
            for list_obj in self.board.list_objects():
                lists_container.add_widget(ListWidget(list_name=list_obj.name, board_widget=self))

    def add_new_list_popup(self):
        TextInputPopup(title="Add New List", hint_text="Enter list name", callback=self.add_new_list_callback).open()

    def add_new_list_callback(self, list_name):
        if list_name and self.board.create_list(list_name):
            App.get_running_app().workspace_manager.save_current_workspace()
            self.populate_lists()
        elif list_name:
            App.get_running_app().show_toast(f"List '{list_name}' already exists.")


class BinItem(BoxLayout):
    item_name = StringProperty('')
    item_type = StringProperty('')
    bin_screen = ObjectProperty(None)


class WorkspaceScreen(Screen):
    def on_enter(self, *_):
        Clock.schedule_once(self.populate_grid)

    def populate_grid(self, *_):
        try:
            self.ids.workspaces_grid.clear_widgets()
            app = App.get_running_app()
            workspaces_data = app.workspace_manager.workspaces()
            sorted_workspaces = sorted(workspaces_data.items(), key=lambda item: item[1].get('last_edited', ''), reverse=True)

            for name, data in sorted_workspaces:
                iso = data.get("last_edited", datetime.datetime.now().isoformat())
                try:
                    dt = datetime.datetime.fromisoformat(iso)
                    date_str = dt.strftime('%Y-%m-%d')
                    time_str = dt.strftime('%H:%M')
                except (ValueError, TypeError):
                    date_str = "Unknown"
                    time_str = ""

                self.ids.workspaces_grid.add_widget(
                    WorkspaceCard(
                        workspace_name=name,
                        app=app,
                        last_edited_date=date_str,
                        last_edited_time=time_str
                    )
                )
        except Exception as e:
            print(f"ERROR in populate_grid: {e}\n{traceback.format_exc()}")
            App.get_running_app().show_toast(f"Error: {e}")

class BoardScreen(Screen):

    def on_enter(self, *_):
        self.load_current_board()

    def load_current_board(self, *_):
        app = App.get_running_app()
        workspace = app.workspace_manager.current_workspace()
        if not workspace:
            self.go_back_to_workspaces()
            return

        board = workspace.selected_board()
        if not board:
            # This could happen if the last board was deleted. Create a new one.
            workspace.create_board()
            workspace.set_selected_board_by_index(0)
            board = workspace.selected_board()
            app.workspace_manager.save_current_workspace()

        self.ids.board_container.clear_widgets()
        self.ids.board_container.add_widget(BoardWidget(board=board))
        self.update_indicator()

    def load_next_board(self):
        workspace = App.get_running_app().workspace_manager.current_workspace()
        if not workspace:
            return

        current_index = workspace._selected_board_index
        if current_index < len(workspace._boards) - 1:
            workspace.set_selected_board_by_index(current_index + 1)
            self.load_current_board()
        else:
            CreateBoardDialog(board_screen=self).open()

    def load_previous_board(self):
        workspace = App.get_running_app().workspace_manager.current_workspace()
        if not workspace:
            return

        if workspace._selected_board_index > 0:
            workspace.set_selected_board_by_index(workspace._selected_board_index - 1)
            self.load_current_board()

    def update_indicator(self):
        workspace = App.get_running_app().workspace_manager.current_workspace()
        if not workspace or not workspace._boards:
            self.ids.board_indicator_label.text = "No Boards"
            return

        index = workspace._selected_board_index
        board = workspace.selected_board()
        self.ids.board_indicator_label.text = f"{board.name} ({index + 1}/{len(workspace._boards)})"

    def create_new_board_and_load_it(self):
        app = App.get_running_app()
        workspace = app.workspace_manager.current_workspace()
        if not workspace:
            return

        new_board = workspace.create_board()
        workspace.set_selected_board_by_index(len(workspace._boards) - 1)
        app.workspace_manager.save_current_workspace()
        app.show_toast(f"Created '{new_board.name}'")
        self.load_current_board()

    def rename_current_board_popup(self):
        workspace = App.get_running_app().workspace_manager.current_workspace()
        if workspace and (current_board := workspace.selected_board()):
            TextInputPopup(
                title="Rename Board",
                hint_text=current_board.name,
                callback=self.rename_current_board_callback
            ).open()

    def rename_current_board_callback(self, new_name):
        workspace = App.get_running_app().workspace_manager
        app = App.get_running_app()

        if not new_name or not workspace.current_workspace():
            return

        board = workspace.current_workspace().selected_board()
        if not board:
            return

        if board.rename_board(new_name):
            workspace.save_current_workspace()
            self.update_indicator()
            app.show_toast("Board renamed")

    def add_new_list_to_current_board(self):
        if self.ids.board_container.children:
            current_widget = self.ids.board_container.children[0]
            if isinstance(current_widget, BoardWidget):
                current_widget.add_new_list_popup()

    def open_board_options(self):
        BoardOptionsDialog(board_screen=self).open()

    def go_back_to_workspaces(self):
        app = App.get_running_app()
        if app.workspace_manager.current_workspace():
            app.workspace_manager.save_current_workspace()
            app.workspace_manager.close_current_workspace()

        self.manager.transition.direction = 'right'
        self.manager.current = 'workspaces'


class BinScreen(Screen):
    def on_enter(self, *_):
        self.populate_bin()

    def populate_bin(self):
        self.ids.bin_items_grid.clear_widgets()
        workspace = App.get_running_app().workspace_manager.current_workspace()

        if not workspace: return
        board = workspace.selected_board()
        if not board: return

        for l in board.bin.get_deleted_lists():
            self.ids.bin_items_grid.add_widget(
                BinItem(item_name=l.name, item_type='list', bin_screen=self)
            )

    def restore_item(self, item_name, item_type):
        workspace = App.get_running_app().workspace_manager.current_workspace()
        if not workspace: return
        board = workspace.selected_board()
        if not board: return

        if item_type == 'list':
            restored_list = board.bin.restore_list(item_name)
            if restored_list:
                board.add_list(restored_list)
                App.get_running_app().workspace_manager.save_current_workspace()
                self.populate_bin()

    def delete_item_permanently(self, item_name, item_type):
        workspace = App.get_running_app().workspace_manager.current_workspace()
        if not workspace: return
        board = workspace.selected_board()
        if not board: return

        if item_type == 'list' and board.bin.permanently_delete_list(item_name):
            App.get_running_app().workspace_manager.save_current_workspace()
            self.populate_bin()

    def go_back_to_board(self):
        self.manager.get_screen('board').load_current_board()
        self.manager.current = 'board'


class KanbanApp(App):
    def build(self):
        self.workspace_manager = WorkspaceManager()
        # The kv file should be named 'kanban.kv' to be loaded automatically
        # or loaded explicitly like this.
        Builder.load_file('app.kv')
        self.sm = ScreenManager(transition=SlideTransition())

        with self.sm.canvas.before:
            Color(rgba=APP_COLORS['background'])
            self.background_rect = Rectangle(size=self.sm.size, pos=self.sm.pos)

        self.sm.bind(pos=self.update_background_rect, size=self.update_background_rect)
        self.sm.add_widget(WorkspaceScreen(name='workspaces'))
        self.sm.add_widget(BoardScreen(name='board'))
        self.sm.add_widget(BinScreen(name='bin_screen'))
        return self.sm

    def update_background_rect(self, instance, value):
        self.background_rect.pos = instance.pos
        self.background_rect.size = instance.size

    def show_toast(self, text):
        try:
            Toast(text=str(text)).open()
        except Exception as e:
            print(f"--- FAILED TO CREATE TOAST ---\n{text}\n{e}\n{traceback.format_exc()}")

    def open_workspace(self, workspace_name):
        try:
            if self.workspace_manager.is_workspace_encrypted(workspace_name):
                TextInputPopup(
                    title=f"Password for {workspace_name}",
                    hint_text="Enter password",
                    is_password=True,
                    callback=lambda p: self.open_workspace_callback(workspace_name, p)
                ).open()
            elif self.workspace_manager.open_workspace(workspace_name):
                self.sm.transition.direction = 'left'
                self.sm.current = 'board'
        except Exception as e:
            self.show_toast(f"Error opening: {e}")
            print(traceback.format_exc())

    def open_workspace_callback(self, workspace_name, password):
        try:
            workspace = self.workspace_manager.open_workspace(workspace_name, password=password)
            if workspace and workspace != "password_required":
                self.sm.transition.direction = 'left'
                self.sm.current = 'board'
            else:
                self.show_toast("Incorrect password.")
        except Exception as e:
            self.show_toast(f"Error with password: {e}")
            print(traceback.format_exc())

    def create_new_workspace(self):
        TextInputPopup(
            title="Create Workspace",
            hint_text="Enter name",
            callback=self.create_workspace_callback
        ).open()

    def create_workspace_callback(self, name):
        try:
            if not name:
                self.show_toast("Name cannot be empty.")
                return

            if self.workspace_manager.create_workspace(name):
                self.show_toast(f"Workspace '{name}' created.")
                self.sm.get_screen('workspaces').populate_grid()
            else:
                self.show_toast(f"'{name}' already exists.")
        except Exception as e:
            self.show_toast(f"Failed to create: {e}")
            print(traceback.format_exc())

    def delete_workspace(self, workspace_name):
        try:
            if self.workspace_manager.delete_workspace(workspace_name):
                self.show_toast(f"'{workspace_name}' deleted.")
                self.sm.get_screen('workspaces').populate_grid()
            else:
                self.show_toast("Error deleting workspace.")
        except Exception as e:
            self.show_toast(f"Failed to delete: {e}")
            print(traceback.format_exc())

    def rename_workspace(self, old_name):
        try:
            if self.workspace_manager.is_workspace_encrypted(old_name):
                TextInputPopup(
                    title=f"Password for {old_name}",
                    hint_text="Enter password to rename",
                    is_password=True,
                    callback=lambda p: self.rename_password_check_callback(old_name, p)
                ).open()
            else:
                TextInputPopup(
                    title="Rename Workspace",
                    hint_text="Enter new name",
                    callback=lambda n: self.rename_workspace_callback(old_name, n)
                ).open()
        except Exception as e:
            self.show_toast(f"Error renaming: {e}")
            print(traceback.format_exc())

    def rename_password_check_callback(self, old_name, password):
        try:
            workspace = self.workspace_manager.open_workspace(old_name, password=password)
            if workspace and workspace != "password_required":
                self.workspace_manager.close_current_workspace()
                TextInputPopup(
                    title="Rename Workspace",
                    hint_text="Enter new name",
                    callback=lambda n: self.rename_workspace_callback(old_name, n, password)
                ).open()
            else:
                self.show_toast("Incorrect password.")
        except Exception as e:
            self.show_toast(f"Password check failed: {e}")
            print(traceback.format_exc())

    _RENAME_IN_PROGRESS = False

    def rename_workspace_callback(self, old_name, new_name, password=None):
        if self._RENAME_IN_PROGRESS:
            return

        self._RENAME_IN_PROGRESS = True
        try:
            if not new_name:
                self.show_toast("New name cannot be empty.")
                return

            if self.workspace_manager.rename_workspace(old_name, new_name, password=password):
                self.show_toast(f"Renamed to '{new_name}'.")
                self.sm.get_screen('workspaces').populate_grid()
            else:
                self.show_toast(f"Failed to rename.")
        except Exception as e:
            self.show_toast(f"Failed to rename: {e}")
            print(traceback.format_exc())
        finally:
            self._RENAME_IN_PROGRESS = False

    def set_workspace_password(self, workspace_name):
        try:
            if self.workspace_manager.is_workspace_encrypted(workspace_name):
                TextInputPopup(
                    title="Confirm Current Password",
                    hint_text="Enter password",
                    is_password=True,
                    callback=lambda p: self.change_password_confirm_callback(workspace_name, p)
                ).open()
            else:
                TextInputPopup(
                    title="Set New Password",
                    hint_text="Enter new password",
                    is_password=True,
                    callback=lambda p: self.set_password_callback(workspace_name, p, is_new=True)
                ).open()
        except Exception as e:
            self.show_toast(f"Error: {e}")
            print(traceback.format_exc())

    def change_password_confirm_callback(self, workspace_name, current_password):
        try:
            workspace = self.workspace_manager.open_workspace(workspace_name, password=current_password)
            if workspace and workspace != "password_required":
                self.workspace_manager.close_current_workspace()
                TextInputPopup(
                    title="Enter New Password",
                    hint_text="Leave blank to remove",
                    is_password=True,
                    callback=lambda n: self.set_password_callback(workspace_name, n, current_password=current_password)
                ).open()
            else:
                self.show_toast("Incorrect password.")
        except Exception as e:
            self.show_toast(f"Password confirmation failed: {e}")
            print(traceback.format_exc())

    def set_password_callback(self, workspace_name, password, is_new=False, current_password=None):
        try:
            workspace = self.workspace_manager.open_workspace(
                workspace_name,
                password=(current_password if not is_new else None)
            )
            if workspace and workspace != "password_required":
                workspace.set_password(password)
                self.workspace_manager.save_current_workspace()
                self.workspace_manager.close_current_workspace()
                self.show_toast("Password updated.")
                self.sm.get_screen('workspaces').populate_grid()
            else:
                self.show_toast("Could not update password.")
        except Exception as e:
            self.show_toast(f"Failed to set password: {e}")
            print(traceback.format_exc())

if __name__ == '__main__':
    KanbanApp().run()