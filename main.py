# main.py
# ---------------------------------------------------------------
# A minimal Trello-like “workspace” app with optional encryption.
# ---------------------------------------------------------------

import base64
import datetime
import json
import os
import shutil
from functools import partial

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

# --- Configuration ----------------------------------------------------------

DEFAULT_WORKSPACES_DIR = "workspaces"
CONFIG_FILE_NAME = "workspaces.json"
DATA_FILE_NAME = "data.json"
SALT_SIZE = 16

# --- Encryption helper ------------------------------------------------------


class EncryptionHelper:
    """Handles encryption and decryption operations using Fernet."""

    @staticmethod
    def derive_key(password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
            backend=default_backend(),
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))

    @staticmethod
    def encrypt(data_str: str, password: str) -> bytes:
        salt = os.urandom(SALT_SIZE)
        key = EncryptionHelper.derive_key(password, salt)
        encrypted = Fernet(key).encrypt(data_str.encode("utf-8"))
        return salt + encrypted

    @staticmethod
    def decrypt(encrypted_data: bytes, password: str) -> str:
        if len(encrypted_data) <= SALT_SIZE:
            raise ValueError("Invalid encrypted data: too short for salt.")
        salt = encrypted_data[:SALT_SIZE]
        ciphertext = encrypted_data[SALT_SIZE:]
        key = EncryptionHelper.derive_key(password, salt)
        return Fernet(key).decrypt(ciphertext).decode("utf-8")


# --- Basic data containers --------------------------------------------------


class Board:
    def __init__(self, name: str = "Default Board", lists=None):
        self.name = name
        self.lists = lists if lists is not None else []

    def to_dict(self):
        return {"name": self.name, "lists": self.lists}

    @classmethod
    def from_dict(cls, data: dict):
        return cls(name=data.get("name"), lists=data.get("lists", []))


class Workspace:
    def __init__(self, name: str, password: str | None = None, path: str | None = None):
        self.name = name
        self.path = path
        self._password = password
        self.last_edited = datetime.datetime.now().astimezone()
        self.board = Board(name=f"{name} Board")

    # ---- password handling --------------------------------------------------

    def set_password(self, new_password: str | None):
        self._password = new_password.strip() if new_password else None
        return (
            f"Password has been {'set' if self._password else 'cleared'} "
            "for this session. Save the workspace to apply the change "
            "permanently."
        )

    # ---- (de)serialization --------------------------------------------------

    def to_dict(self):
        return {
            "name": self.name,
            "last_edited": self.last_edited.isoformat(),
            "board": self.board.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict, path: str):
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


# --- Workspace manager ------------------------------------------------------


class WorkspaceManager:
    """Main controller for creating, opening, and saving workspaces."""

    def __init__(self, config_path: str, workspaces_dir: str):
        self.workspaces_dir = workspaces_dir
        self.config_path = config_path
        self.workspaces: dict[str, str] = {}
        self.current_workspace: Workspace | None = None

        os.makedirs(self.workspaces_dir, exist_ok=True)
        self._load_master_config()

    # ---- master config helpers ---------------------------------------------

    def _load_master_config(self):
        if not os.path.exists(self.config_path):
            self.workspaces = {}
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as fp:
                self.workspaces = json.load(fp)
            self._clean_invalid_workspaces()
        except (IOError, json.JSONDecodeError):
            self.workspaces = {}

    def _save_master_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as fp:
                json.dump(self.workspaces, fp, indent=2)
        except IOError as err:
            print(f"Error: Could not save master config: {err}")

    def _clean_invalid_workspaces(self):
        initial = len(self.workspaces)
        self.workspaces = {
            name: path
            for name, path in self.workspaces.items()
            if os.path.isdir(path)
            and os.path.exists(os.path.join(path, DATA_FILE_NAME))
        }
        if len(self.workspaces) != initial:
            self._save_master_config()

    # ---- create / open / save / close --------------------------------------

    def create_workspace(self, name: str):
        if not name or name in self.workspaces:
            return None, f"Error: Invalid or duplicate workspace name '{name}'."

        path = os.path.join(self.workspaces_dir, name)
        if os.path.exists(path):
            return None, f"Error: Directory '{path}' already exists."

        try:
            os.makedirs(path)
            ws = Workspace(name, path=path)
            self.current_workspace = ws
            self.save_current_workspace()

            self.workspaces[name] = path
            self._save_master_config()
            return ws, f"Successfully created and opened workspace: {name}"
        except OSError as err:
            return None, f"Error creating workspace: {err}"

    # -------- encryption probe ----------------------------------------------

    def is_workspace_encrypted(self, name: str) -> bool:
        if name not in self.workspaces:
            return False
        data_path = os.path.join(self.workspaces[name], DATA_FILE_NAME)
        try:
            with open(data_path, "rb") as fp:
                json.loads(fp.read(1024).decode("utf-8"))
            return False
        except (UnicodeDecodeError, json.JSONDecodeError):
            return True
        except IOError:
            return False

    # -------- open -----------------------------------------------------------

    def open_workspace(self, name: str, password: str | None = None):
        if self.current_workspace:
            return (
                None,
                f"Please close the current workspace "
                f"('{self.current_workspace.name}') first.",
            )

        if name not in self.workspaces:
            return None, f"Error: Workspace '{name}' not found."

        data_path = os.path.join(self.workspaces[name], DATA_FILE_NAME)

        try:
            with open(data_path, "rb") as fp:
                raw = fp.read()

            is_encrypted = self.is_workspace_encrypted(name)
            if is_encrypted and not password:
                return (
                    None,
                    "Error: This workspace is encrypted and requires a password.",
                )

            data_str = (
                EncryptionHelper.decrypt(raw, password)
                if is_encrypted
                else raw.decode("utf-8")
            )
            ws_data = json.loads(data_str)

            ws = Workspace.from_dict(ws_data, self.workspaces[name])
            ws._password = password
            self.current_workspace = ws
            return ws, f"Successfully opened workspace: {name}"

        except InvalidToken:
            return None, "Error: Incorrect password or corrupted data file."
        except (IOError, json.JSONDecodeError, ValueError) as err:
            return None, f"Error opening workspace '{name}': {err}"

    # -------- save -----------------------------------------------------------

    def save_current_workspace(self):
        if not self.current_workspace:
            return "No active workspace to save."

        ws = self.current_workspace
        ws.last_edited = datetime.datetime.now(datetime.timezone.utc)

        data_path = os.path.join(ws.path, DATA_FILE_NAME)
        json_data = json.dumps(ws.to_dict(), indent=2)

        try:
            if ws._password:
                enc = EncryptionHelper.encrypt(json_data, ws._password)
                with open(data_path, "wb") as fp:
                    fp.write(enc)
            else:
                with open(data_path, "w", encoding="utf-8") as fp:
                    fp.write(json_data)
            return f"Workspace '{ws.name}' saved successfully."
        except IOError as err:
            return f"Error saving workspace: {err}"

    # -------- close ----------------------------------------------------------

    def close_current_workspace(self):
        if not self.current_workspace:
            return "No workspace is currently open."
        name = self.current_workspace.name
        self.current_workspace = None
        return f"Workspace '{name}' has been closed."

    # -------- convenience ----------------------------------------------------

    def list_workspaces(self):
        return list(self.workspaces.keys())


# --- Kivy UI ----------------------------------------------------------------

KV = """
<WorkspaceButton>:
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


class WorkspaceButton(Button):
    """Real Python subclass so we can instantiate it from code."""
    pass


class StatusPopup(Popup):
    pass


class InputDialog(Popup):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ids.confirm_button.bind(on_press=self._on_confirm)
        self.callback = None

    def _on_confirm(self, _instance):
        if self.callback:
            self.callback(self.ids.text_input.text)
        self.dismiss()


# --- Application ------------------------------------------------------------


class WorkspaceApp(App):
    def build(self):
        # Use app-specific directory on mobile / desktop
        self.user_dir = self.user_data_dir
        workspaces_dir = os.path.join(self.user_dir, DEFAULT_WORKSPACES_DIR)
        config_path = os.path.join(self.user_dir, CONFIG_FILE_NAME)

        self.manager = WorkspaceManager(
            config_path=config_path, workspaces_dir=workspaces_dir
        )
        self.sm = Builder.load_string(KV)
        return self.sm

    # ---------- helpers ------------------------------------------------------

    def show_status(self, message: str):
        popup = StatusPopup()
        popup.ids.status_message.text = message
        popup.open()

    # ---------- main screen --------------------------------------------------

    def on_start(self):
        self.populate_workspaces()

    def populate_workspaces(self, *_):
        layout = self.sm.get_screen("main").ids.workspace_list
        layout.clear_widgets()

        names = self.manager.list_workspaces()
        if not names:
            layout.add_widget(Label(text="No workspaces found. Create one!"))
            return

        for name in names:
            btn = WorkspaceButton(text=name)
            btn.bind(on_press=partial(self._maybe_open_workspace, name))
            layout.add_widget(btn)

    # ---------- create -------------------------------------------------------

    def show_create_workspace_dialog(self):
        dlg = InputDialog(title="Create Workspace")
        dlg.ids.prompt_label.text = "Enter new workspace name:"
        dlg.callback = self._create_workspace
        dlg.open()

    def _create_workspace(self, name: str):
        if not name:
            self.show_status("Workspace name cannot be empty.")
            return
        ws, msg = self.manager.create_workspace(name)
        self.show_status(msg)
        if ws:
            self.populate_workspaces()
            self._go_to_workspace_screen()

    # ---------- open ---------------------------------------------------------

    def _maybe_open_workspace(self, name: str, _instance):
        if self.manager.is_workspace_encrypted(name):
            dlg = InputDialog(title=f"Open '{name}'")
            dlg.ids.prompt_label.text = "Enter password:"
            dlg.ids.text_input.password = True
            dlg.callback = lambda pwd: self._open_workspace(name, pwd)
            dlg.open()
        else:
            self._open_workspace(name, None)

    def _open_workspace(self, name: str, pwd: str | None):
        ws, msg = self.manager.open_workspace(name, pwd)
        self.show_status(msg)
        if ws:
            self._go_to_workspace_screen()

    # ---------- workspace screen --------------------------------------------

    def _go_to_workspace_screen(self):
        ws = self.manager.current_workspace
        screen: WorkspaceScreen = self.sm.get_screen("workspace")
        screen.ids.ws_name_label.text = f"Workspace: {ws.name}"
        screen.ids.board_content.text = json.dumps(ws.board.to_dict(), indent=2)
        self.sm.current = "workspace"

    def save_workspace(self):
        if not self.manager.current_workspace:
            return
        screen: WorkspaceScreen = self.sm.get_screen("workspace")
        try:
            board_dict = json.loads(screen.ids.board_content.text)
            self.manager.current_workspace.board = Board.from_dict(board_dict)
        except json.JSONDecodeError:
            self.show_status("Error: Invalid JSON format in board content.")
            return
        self.show_status(self.manager.save_current_workspace())

    # ---------- set / clear password ----------------------------------------

    def show_set_password_dialog(self):
        dlg = InputDialog(title="Set Password")
        dlg.ids.prompt_label.text = (
            "Enter new password (leave blank to clear):"
        )
        dlg.ids.text_input.password = True
        dlg.callback = self._set_password
        dlg.open()

    def _set_password(self, pwd: str):
        if not self.manager.current_workspace:
            return
        msg = self.manager.current_workspace.set_password(pwd)
        self.show_status(msg)

    # ---------- close --------------------------------------------------------

    def close_workspace(self):
        msg = self.manager.close_current_workspace()
        self.show_status(msg)
        self.sm.current = "main"
        self.populate_workspaces()


if __name__ == "__main__":
    WorkspaceApp().run()