import os
import json
import datetime
import base64
import shutil
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

# --- Your Backend Code (with minor adjustments for GUI integration) ---
# I've moved the print statements to be returned as status messages
# so the GUI can display them in popups.

# --- Configuration ---
DEFAULT_WORKSPACES_DIR = "workspaces"
CONFIG_FILE_NAME = "workspaces.json"
DATA_FILE_NAME = "data.json"
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
            backend=default_backend(),
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))

    @staticmethod
    def encrypt(data_str, password):
        salt = os.urandom(SALT_SIZE)
        key = EncryptionHelper.derive_key(password, salt)
        encrypted = Fernet(key).encrypt(data_str.encode("utf-8"))
        return salt + encrypted

    @staticmethod
    def decrypt(encrypted_data, password):
        if len(encrypted_data) <= SALT_SIZE:
            raise ValueError("Invalid encrypted data: too short for salt.")
        salt = encrypted_data[:SALT_SIZE]
        ciphertext = encrypted_data[SALT_SIZE:]
        key = EncryptionHelper.derive_key(password, salt)
        return Fernet(key).decrypt(ciphertext).decode("utf-8")


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
        return (
            f"Password has been {'set' if self._password else 'cleared'} for this session. "
            "Save the workspace to apply the change permanently."
        )

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
                workspace.last_edited = datetime.datetime.fromisoformat(
                    last_edited_str
                )
            except ValueError:
                pass
        if board_data := data.get("board"):
            workspace.board = Board.from_dict(board_data)
        return workspace


class WorkspaceManager:
    """The main controller for creating, opening, and saving workspaces."""

    def __init__(
        self,
        config_path=CONFIG_FILE_NAME,
        workspaces_dir=DEFAULT_WORKSPACES_DIR,
    ):
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
        except (IOError, json.JSONDecodeError):
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
            name: path
            for name, path in self.workspaces.items()
            if os.path.isdir(path)
            and os.path.exists(os.path.join(path, DATA_FILE_NAME))
        }
        if len(self.workspaces) != initial_count:
            self._save_master_config()

    def create_workspace(self, name):
        if not name or name in self.workspaces:
            return None, f"Error: Invalid or duplicate workspace name '{name}'."

        path = os.path.join(self.workspaces_dir, name)
        if os.path.exists(path):
            return None, f"Error: Directory '{path}' already exists."

        try:
            os.makedirs(path)
            workspace = Workspace(name, path=path)
            self.current_workspace = workspace
            self.save_current_workspace()

            self.workspaces[name] = path
            self._save_master_config()
            return workspace, f"Successfully created and opened workspace: {name}"
        except OSError as e:
            return None, f"Error creating workspace: {e}"

    def is_workspace_encrypted(self, name):
        """Check if a workspace file is likely encrypted without reading it."""
        if name not in self.workspaces:
            return False
        path = self.workspaces[name]
        data_path = os.path.join(path, DATA_FILE_NAME)
        try:
            with open(data_path, "rb") as f:
                # Try to decode the first few bytes as JSON. If it fails, it's likely binary/encrypted.
                json.loads(f.read(1024).decode("utf-8"))
            return False
        except (UnicodeDecodeError, json.JSONDecodeError):
            return True
        except (IOError):
            return False

    def open_workspace(self, name, password=None):
        """Opens a workspace, using the provided password if necessary."""
        if self.current_workspace:
            return (
                None,
                f"Please close the current workspace ('{self.current_workspace.name}') first.",
            )
        if name not in self.workspaces:
            return None, f"Error: Workspace '{name}' not found."

        path = self.workspaces[name]
        data_path = os.path.join(path, DATA_FILE_NAME)

        try:
            with open(data_path, "rb") as f:
                file_content = f.read()

            is_encrypted = self.is_workspace_encrypted(name)
            if is_encrypted and not password:
                return (
                    None,
                    "Error: This workspace is encrypted and requires a password.",
                )

            data_str = (
                EncryptionHelper.decrypt(file_content, password)
                if is_encrypted
                else file_content.decode("utf-8")
            )
            workspace_data = json.loads(data_str)

            workspace = Workspace.from_dict(workspace_data, path)
            workspace._password = password
            self.current_workspace = workspace
            return workspace, f"Successfully opened workspace: {name}"

        except InvalidToken:
            return None, "Error: Incorrect password or corrupted data file."
        except (IOError, json.JSONDecodeError, ValueError) as e:
            return None, f"Error opening workspace '{name}': {e}"

    def save_current_workspace(self):
        if not self.current_workspace:
            return "No active workspace to save."

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
                with open(data_path, "w", encoding="utf-8") as f:
                    f.write(json_data)
            return f"Workspace '{ws.name}' saved successfully."
        except IOError as e:
            return f"Error saving workspace: {e}"

    def close_current_workspace(self):
        if not self.current_workspace:
            return "No workspace is currently open."
        name = self.current_workspace.name
        self.current_workspace = None
        return f"Workspace '{name}' has been closed."

    def list_workspaces(self):
        return list(self.workspaces.keys())


# --- Kivy Frontend App ---

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.lang import Builder
from kivy.clock import Clock
from functools import partial

# Kivy Language string for UI layout
KV = """
<WorkspaceButton@Button>:
    size_hint_y: None
    height: '48dp'

<StatusPopup>:
    size_hint: 0.8, 0.4
    title: "Status"
    BoxLayout:
        orientation: 'vertical'
        padding: '10dp'
        spacing: '10dp'
        Label:
            id: status_message
            text: ''
            size_hint_y: 0.8
        Button:
            text: 'Close'
            size_hint_y: 0.2
            on_press: root.dismiss()

<InputDialog>:
    size_hint: 0.9, 0.4
    auto_dismiss: False
    BoxLayout:
        orientation: 'vertical'
        padding: '10dp'
        spacing: '10dp'
        Label:
            id: prompt_label
            text: 'Enter value:'
        TextInput:
            id: text_input
            multiline: False
        BoxLayout:
            size_hint_y: None
            height: '48dp'
            Button:
                text: 'Cancel'
                on_press: root.dismiss()
            Button:
                id: confirm_button
                text: 'Confirm'

ScreenManager:
    MainScreen:
        name: 'main'
    WorkspaceScreen:
        name: 'workspace'

<MainScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: '10dp'
        spacing: '10dp'
        Label:
            text: 'Available Workspaces'
            font_size: '24sp'
            size_hint_y: None
            height: '40dp'
        ScrollView:
            GridLayout:
                id: workspace_list
                cols: 1
                size_hint_y: None
                height: self.minimum_height
                spacing: '5dp'
        BoxLayout:
            size_hint_y: None
            height: '48dp'
            spacing: '10dp'
            Button:
                text: 'Create New'
                on_press: app.show_create_workspace_dialog()
            Button:
                text: 'Refresh List'
                on_press: app.populate_workspaces()

<WorkspaceScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: '10dp'
        spacing: '10dp'
        Label:
            id: ws_name_label
            text: 'Workspace: '
            font_size: '24sp'
            size_hint_y: None
            height: '40dp'
        TextInput:
            id: board_content
            hint_text: 'Board content (JSON format)'
        GridLayout:
            cols: 3
            size_hint_y: None
            height: '48dp'
            spacing: '10dp'
            Button:
                text: 'Save'
                on_press: app.save_workspace()
            Button:
                text: 'Set/Clear Pwd'
                on_press: app.show_set_password_dialog()
            Button:
                text: 'Close'
                on_press: app.close_workspace()
"""


class MainScreen(Screen):
    pass


class WorkspaceScreen(Screen):
    pass


class StatusPopup(Popup):
    pass


class InputDialog(Popup):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ids.confirm_button.bind(on_press=self.on_confirm)
        self.callback = None

    def on_confirm(self, instance):
        if self.callback:
            self.callback(self.ids.text_input.text)
        self.dismiss()


class WorkspaceApp(App):
    def build(self):
        # --- Android-Safe File Paths ---
        self.user_dir = self.user_data_dir
        workspaces_dir = os.path.join(self.user_dir, DEFAULT_WORKSPACES_DIR)
        config_path = os.path.join(self.user_dir, CONFIG_FILE_NAME)

        self.manager = WorkspaceManager(
            config_path=config_path, workspaces_dir=workspaces_dir
        )
        self.sm = Builder.load_string(KV)
        return self.sm

    def on_start(self):
        self.populate_workspaces()

    def show_status(self, message):
        popup = StatusPopup()
        popup.ids.status_message.text = message
        popup.open()

    def populate_workspaces(self):
        ws_list_layout = self.sm.get_screen("main").ids.workspace_list
        ws_list_layout.clear_widgets()
        workspaces = self.manager.list_workspaces()
        if not workspaces:
            ws_list_layout.add_widget(
                Label(text="No workspaces found. Create one!")
            )
        for name in workspaces:
            btn = WorkspaceButton(text=name)
            btn.bind(on_press=partial(self.try_open_workspace, name))
            ws_list_layout.add_widget(btn)

    def show_create_workspace_dialog(self):
        dialog = InputDialog(title="Create Workspace")
        dialog.ids.prompt_label.text = "Enter new workspace name:"
        dialog.callback = self.create_workspace
        dialog.open()

    def create_workspace(self, name):
        if not name:
            self.show_status("Workspace name cannot be empty.")
            return
        ws, msg = self.manager.create_workspace(name)
        self.show_status(msg)
        if ws:
            self.populate_workspaces()
            self.go_to_workspace_screen()

    def try_open_workspace(self, name, instance=None):
        if self.manager.is_workspace_encrypted(name):
            dialog = InputDialog(title=f"Open '{name}'")
            dialog.ids.prompt_label.text = "Enter password:"
            dialog.ids.text_input.password = True
            dialog.callback = lambda password: self.open_workspace(
                name, password
            )
            dialog.open()
        else:
            self.open_workspace(name, None)

    def open_workspace(self, name, password):
        ws, msg = self.manager.open_workspace(name, password)
        self.show_status(msg)
        if ws:
            self.go_to_workspace_screen()

    def go_to_workspace_screen(self):
        ws = self.manager.current_workspace
        screen = self.sm.get_screen("workspace")
        screen.ids.ws_name_label.text = f"Workspace: {ws.name}"
        # For this test app, we'll just show the board data as pretty-printed JSON
        board_json = json.dumps(ws.board.to_dict(), indent=2)
        screen.ids.board_content.text = board_json
        self.sm.current = "workspace"

    def save_workspace(self):
        if not self.manager.current_workspace:
            return
        screen = self.sm.get_screen("workspace")
        board_content_str = screen.ids.board_content.text
        try:
            # Update the board object from the text input before saving
            board_data = json.loads(board_content_str)
            self.manager.current_workspace.board = Board.from_dict(board_data)
            msg = self.manager.save_current_workspace()
            self.show_status(msg)
        except json.JSONDecodeError:
            self.show_status("Error: Invalid JSON format in board content.")

    def show_set_password_dialog(self):
        dialog = InputDialog(title="Set Password")
        dialog.ids.prompt_label.text = (
            "Enter new password (leave blank to clear):"
        )
        dialog.ids.text_input.password = True
        dialog.callback = self.set_password
        dialog.open()

    def set_password(self, password):
        if not self.manager.current_workspace:
            return
        msg = self.manager.current_workspace.set_password(password)
        self.show_status(msg)

    def close_workspace(self):
        msg = self.manager.close_current_workspace()
        self.show_status(msg)
        self.sm.current = "main"
        self.populate_workspaces()


if __name__ == "__main__":
    WorkspaceApp().run()