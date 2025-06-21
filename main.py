import datetime
import traceback
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import ObjectProperty, StringProperty, BooleanProperty
from kivy.clock import Clock
from kivy.uix.modalview import ModalView
from kivy.uix.label import Label
from kivy.metrics import dp
from kivy.utils import get_color_from_hex
from kivy.graphics import Color, Rectangle
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior

from app_classes import WorkspaceManager

APP_COLORS = {
    "background": get_color_from_hex("#FAFAFA"),
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

# --- SIMPLIFIED TOAST CLASS ---
# Now that the kv rule is fixed, this class can be very simple again.
class Toast(ModalView):
    text = StringProperty('')

    def __init__(self, text, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        Clock.schedule_once(self.dismiss, 0.7) # You can adjust the duration


class TextInputPopup(ModalView):
    # This class remains the same
    title = StringProperty("Enter Value")
    hint_text = StringProperty("")
    callback = ObjectProperty(None)
    is_password = BooleanProperty(False)
    
    def on_submit(self, text_input):
        if self.callback: self.callback(text_input)
        self.dismiss()

class WorkspaceOptionsDialog(ModalView):
    # This class remains the same
    workspace_name = StringProperty("")
    is_encrypted = BooleanProperty(False)
    
    def __init__(self, workspace_name, **kwargs):
        super().__init__(**kwargs)
        self.workspace_name = workspace_name
        app = App.get_running_app()
        self.is_encrypted = app.workspace_manager.is_workspace_encrypted(self.workspace_name)

# The rest of your main.py file can remain exactly as it was in the previous answer.
# I am including it here for completeness.

class WorkspaceCard(ButtonBehavior, BoxLayout):
    workspace_name = StringProperty('')
    app = ObjectProperty(None)
    last_edited_date = StringProperty('')
    last_edited_time = StringProperty('')
    
    _long_press_event = None

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.cancel_long_press_event()
            self._long_press_event = Clock.schedule_once(self.long_press_callback, 0.3)
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            if self._long_press_event:
                self.cancel_long_press_event()
                self.short_press_callback()
                return True
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
        dialog = WorkspaceOptionsDialog(workspace_name=self.workspace_name)
        dialog.open()


class ListWidget(BoxLayout):
    list_name = StringProperty('')

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
                iso_timestamp = data.get("last_edited", datetime.datetime.now().isoformat())
                try:
                    dt_object = datetime.datetime.fromisoformat(iso_timestamp)
                    date_str = dt_object.strftime('%Y-%m-%d')
                    time_str = dt_object.strftime('%H:%M')
                except (ValueError, TypeError):
                    date_str = "Unknown Date"
                    time_str = ""

                card = WorkspaceCard(
                    workspace_name=name, 
                    app=app,
                    last_edited_date=date_str,
                    last_edited_time=time_str
                )
                self.ids.workspaces_grid.add_widget(card)
        except Exception as e:
            print(f"FATAL ERROR in populate_grid: {e}\n{traceback.format_exc()}")
            App.get_running_app().show_toast(f"Error refreshing workspaces: {e}")


class BoardScreen(Screen):
    workspace_name = StringProperty('Board')

    def on_enter(self, *_):
        Clock.schedule_once(self.populate_board)

    def populate_board(self, *_):
        try:
            self.ids.lists_container.clear_widgets()
            app = App.get_running_app()
            workspace = app.workspace_manager.current_workspace()
            if not workspace:
                self.go_back_to_workspaces()
                return

            self.workspace_name = workspace.name
            board = workspace.selected_board()
            
            self.ids.lists_container.clear_widgets()
            
            if board:
                for list_obj in board.list_objects():
                    list_widget = ListWidget(list_name=list_obj.name)
                    self.ids.lists_container.add_widget(list_widget)
        except Exception as e:
            print(f"FATAL ERROR in populate_board: {e}\n{traceback.format_exc()}")
            App.get_running_app().show_toast(f"Error loading board: {e}")


    def go_back_to_workspaces(self):
        app = App.get_running_app()
        if app.workspace_manager.current_workspace():
            app.workspace_manager.save_current_workspace()
            app.workspace_manager.close_current_workspace()
        self.manager.transition.direction = 'right'
        self.manager.current = 'workspaces'

class KanbanApp(App):
    def build(self):
        self.workspace_manager = WorkspaceManager()
        Builder.load_file('app.kv')
        self.sm = ScreenManager(transition=SlideTransition())

        with self.sm.canvas.before:
            Color(rgba=APP_COLORS['background'])
            self.background_rect = Rectangle(size=self.sm.size, pos=self.sm.pos)

        def update_rect(instance, value):
            self.background_rect.pos = instance.pos
            self.background_rect.size = instance.size

        self.sm.bind(pos=update_rect, size=update_rect)

        self.sm.add_widget(WorkspaceScreen(name='workspaces'))
        self.sm.add_widget(BoardScreen(name='board'))
        return self.sm

    def show_toast(self, text):
        try:
            toast_widget = Toast(text=str(text))
            toast_widget.open()
        except Exception as e:
            print(f"--- FAILED TO CREATE TOAST ---")
            print(f"Original message: {text}")
            print(f"Toast creation error: {e}")
            print(f"{traceback.format_exc()}")

    def open_workspace(self, workspace_name):
        try:
            if self.workspace_manager.is_workspace_encrypted(workspace_name):
                popup = TextInputPopup(
                    title=f"Password for {workspace_name}", hint_text="Enter password", is_password=True,
                    callback=lambda password: self.open_workspace_callback(workspace_name, password)
                )
                popup.open()
            else:
                if self.workspace_manager.open_workspace(workspace_name):
                    self.sm.transition.direction = 'left'
                    self.sm.current = 'board'
        except Exception as e:
            print(f"ERROR in open_workspace: {e}\n{traceback.format_exc()}")
            self.show_toast(f"Error opening workspace: {e}")

    def open_workspace_callback(self, workspace_name, password):
        try:
            workspace = self.workspace_manager.open_workspace(workspace_name, password=password)
            if workspace and workspace != "password_required":
                self.sm.transition.direction = 'left'
                self.sm.current = 'board'
            else:
                self.show_toast("Failed to open workspace. Incorrect password.")
        except Exception as e:
            print(f"ERROR in open_workspace_callback: {e}\n{traceback.format_exc()}")
            self.show_toast(f"Error with password: {e}")

    def create_new_workspace(self):
        popup = TextInputPopup(title="Create Workspace", hint_text="Enter name", callback=self.create_workspace_callback)
        popup.open()
        
    def create_workspace_callback(self, name):
        try:
            if not name:
                self.show_toast("Workspace name cannot be empty.")
                return

            if self.workspace_manager.create_workspace(name):
                self.show_toast(f"Workspace '{name}' created.")
                self.sm.get_screen('workspaces').populate_grid()
            else:
                self.show_toast(f"Workspace '{name}' already exists.")
        except Exception as e:
            print(f"ERROR in create_workspace_callback: {e}\n{traceback.format_exc()}")
            self.show_toast(f"Failed to create workspace: {e}")


    def delete_workspace(self, workspace_name):
        try:
            if self.workspace_manager.delete_workspace(workspace_name):
                self.show_toast(f"Workspace '{workspace_name}' deleted.")
                self.sm.get_screen('workspaces').populate_grid()
            else:
                self.show_toast("Error: Could not delete workspace.")
        except Exception as e:
            print(f"ERROR in delete_workspace: {e}\n{traceback.format_exc()}")
            self.show_toast(f"Failed to delete workspace: {e}")
            
    def rename_workspace(self, old_name):
        try:
            if self.workspace_manager.is_workspace_encrypted(old_name):
                popup = TextInputPopup(
                    title=f"Password for {old_name}", hint_text="Enter current password to rename", is_password=True,
                    callback=lambda password: self.rename_password_check_callback(old_name, password)
                )
                popup.open()
            else:
                popup = TextInputPopup(
                    title="Rename Workspace", hint_text="Enter new name",
                    callback=lambda new_name: self.rename_workspace_callback(old_name, new_name)
                )
                popup.open()
        except Exception as e:
            print(f"ERROR in rename_workspace: {e}\n{traceback.format_exc()}")
            self.show_toast(f"Error renaming: {e}")

    def rename_password_check_callback(self, old_name, password):
        try:
            workspace = self.workspace_manager.open_workspace(old_name, password=password)
            if workspace and workspace != "password_required":
                self.workspace_manager.close_current_workspace()
                popup = TextInputPopup(
                    title="Rename Workspace", hint_text="Enter new name",
                    callback=lambda new_name: self.rename_workspace_callback(old_name, new_name, password)
                )
                popup.open()
            else:
                self.show_toast("Incorrect password. Cannot rename.")
        except Exception as e:
            print(f"ERROR in rename_password_check_callback: {e}\n{traceback.format_exc()}")
            self.show_toast(f"Password check failed: {e}")
            
    def rename_workspace_callback(self, old_name, new_name, password=None):
        try:
            if not new_name:
                self.show_toast("New name cannot be empty.")
                return
            
            if self.workspace_manager.rename_workspace(old_name, new_name, password=password):
                self.show_toast(f"Renamed '{old_name}' to '{new_name}'.")
                self.sm.get_screen('workspaces').populate_grid()
            else:
                self.show_toast(f"Failed to rename. '{new_name}' may already exist.")
        except Exception as e:
            print(f"ERROR in rename_workspace_callback: {e}\n{traceback.format_exc()}")
            self.show_toast(f"Failed to rename workspace: {e}")

    def set_workspace_password(self, workspace_name):
        try:
            if self.workspace_manager.is_workspace_encrypted(workspace_name):
                popup = TextInputPopup(
                    title="Confirm Current Password", hint_text="Enter current password", is_password=True,
                    callback=lambda password: self.change_password_confirm_callback(workspace_name, password)
                )
                popup.open()
            else:
                popup = TextInputPopup(
                    title="Set New Password", hint_text="Enter new password", is_password=True,
                    callback=lambda password: self.set_password_callback(workspace_name, password, is_new=True)
                )
                popup.open()
        except Exception as e:
            print(f"ERROR in set_workspace_password: {e}\n{traceback.format_exc()}")
            self.show_toast(f"Error setting password: {e}")

    def change_password_confirm_callback(self, workspace_name, current_password):
        try:
            workspace = self.workspace_manager.open_workspace(workspace_name, password=current_password)
            if workspace and workspace != "password_required":
                self.workspace_manager.close_current_workspace()
                popup = TextInputPopup(
                    title="Enter New Password", hint_text="Enter new password (or leave blank to remove)", is_password=True,
                    callback=lambda new_password: self.set_password_callback(workspace_name, new_password, current_password=current_password)
                )
                popup.open()
            else:
                self.show_toast("Incorrect current password.")
        except Exception as e:
            print(f"ERROR in change_password_confirm_callback: {e}\n{traceback.format_exc()}")
            self.show_toast(f"Password confirmation failed: {e}")

    def set_password_callback(self, workspace_name, password, is_new=False, current_password=None):
        try:
            auth_password = current_password if not is_new else None
            workspace = self.workspace_manager.open_workspace(workspace_name, password=auth_password)
            
            if workspace and workspace != "password_required":
                workspace.set_password(password)
                self.workspace_manager.save_current_workspace()
                self.workspace_manager.close_current_workspace()
                self.show_toast("Password updated successfully.")
                self.sm.get_screen('workspaces').populate_grid()
            else:
                self.show_toast("An error occurred. Could not update password.")
        except Exception as e:
            print(f"ERROR in set_password_callback: {e}\n{traceback.format_exc()}")
            self.show_toast(f"Failed to set password: {e}")


if __name__ == '__main__':
    KanbanApp().run()