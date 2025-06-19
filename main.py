import json
import os
from functools import partial

# This requires a GUI-compatible WorkspaceManager from app_classes.py
from app_classes import (
    Board,
    WorkspaceManager,
    CONFIG_FILE_NAME,
    DEFAULT_WORKSPACES_DIR,
)

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.textinput import TextInput

# --- Kivy UI Definition (KV) ---

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

# --- Kivy Widget Classes ---

class MainScreen(Screen):
    pass

class WorkspaceScreen(Screen):
    pass

class WorkspaceButton(Button):
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

# --- Main Application Class ---

class WorkspaceApp(App):
    def build(self):
        self.user_dir = self.user_data_dir
        workspaces_dir = os.path.join(self.user_dir, DEFAULT_WORKSPACES_DIR)
        config_path = os.path.join(self.user_dir, CONFIG_FILE_NAME)

        self.manager = WorkspaceManager(
            config_path=config_path, workspaces_dir=workspaces_dir
        )
        self.sm = Builder.load_string(KV)
        return self.sm

    def show_status(self, message: str):
        popup = StatusPopup()
        popup.ids.status_message.text = message
        popup.open()

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

    def show_set_password_dialog(self):
        dlg = InputDialog(title="Set Password")
        dlg.ids.prompt_label.text = "Enter new password (leave blank to clear):"
        dlg.ids.text_input.password = True
        dlg.callback = self._set_password
        dlg.open()

    def _set_password(self, pwd: str):
        if not self.manager.current_workspace:
            return
        msg = self.manager.current_workspace.set_password(pwd)
        self.show_status(msg)

    def close_workspace(self):
        msg = self.manager.close_current_workspace()
        self.show_status(msg)
        self.sm.current = "main"
        self.populate_workspaces()


if __name__ == "__main__":
    WorkspaceApp().run()