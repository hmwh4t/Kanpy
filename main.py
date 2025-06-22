# Standard library imports
import datetime
import traceback
import time

# Kivy framework imports
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import ObjectProperty, StringProperty, BooleanProperty
from kivy.clock import Clock
from kivy.uix.modalview import ModalView
from kivy.metrics import dp
from kivy.utils import get_color_from_hex
from kivy.graphics import Color, Rectangle
from kivy.lang import Builder
from kivy.core.text import LabelBase
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.label import Label
from kivy.uix.button import Button

# Local application-specific imports
from app_classes import WorkspaceManager, Card, Board

# Removed all Android-specific imports (jnius, plyer, platform)

# Application color palette for consistent UI styling
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

# Removed the notification checking function

class Toast(ModalView):
    """A small, temporary popup message (like Android's Toast)."""
    text = StringProperty('')
    def __init__(self, text, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        # Dismiss the toast automatically after a short duration
        Clock.schedule_once(self.dismiss, 1.5)

class TextInputPopup(ModalView):
    """A popup dialog to get text input from the user."""
    title = StringProperty("Enter Value")
    hint_text = StringProperty("")
    callback = ObjectProperty(None)
    is_password = BooleanProperty(False)
    def on_submit(self, text_input):
        """Handles the submission of the text input."""
        if self.callback:
            self.callback(text_input)
        self.dismiss()

class ConfirmationPopup(ModalView):
    """A popup dialog to ask for user confirmation."""
    title = StringProperty("Confirm")
    text = StringProperty("")
    callback = ObjectProperty(None)
    def on_confirm(self):
        """Executes the callback function upon confirmation."""
        if self.callback:
            self.callback()
        self.dismiss()

class CalendarWidget(GridLayout):
    """A widget that displays a calendar for a given month."""
    popup = ObjectProperty(None)
    current_date = ObjectProperty(datetime.date.today())
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cols = 7
        self.bind(current_date=self.update_calendar)
        Clock.schedule_once(lambda dt: self.update_calendar())

    def update_calendar(self, *args):
        """Redraws the calendar grid for the current month and year."""
        self.clear_widgets()
        year = self.current_date.year
        month = self.current_date.month
        today = datetime.date.today()
        # Add day headers (S, M, T, W, T, F, S)
        for day in ['S', 'M', 'T', 'W', 'T', 'F', 'S']:
            self.add_widget(Label(text=day, size_hint_y=None, height=dp(30), color=APP_COLORS['text_secondary']))
        # Calculate the starting day of the week and number of days in the month
        first_day_of_month = datetime.date(year, month, 1).weekday()
        start_day_index = (first_day_of_month + 1) % 7
        num_days_in_month = (datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)).day if month < 12 else 31
        # Add empty labels for days before the 1st of the month
        for _ in range(start_day_index):
            self.add_widget(Label(text=""))
        # Add a button for each day of the month
        for day_num in range(1, num_days_in_month + 1):
            day_date = datetime.date(year, month, day_num)
            day_button = Button(text=str(day_num), on_press=self.select_day, background_color=(0, 0, 0, 0))
            # Style the day buttons based on whether they are in the past, today, or future
            if day_date < today:
                day_button.disabled = True
                day_button.disabled_color = APP_COLORS['text_secondary']
            elif day_date == today:
                day_button.disabled = True
                day_button.disabled_color = APP_COLORS['primary']
                day_button.bold = True
            else:
                day_button.disabled = False
                day_button.color = APP_COLORS['text']
            self.add_widget(day_button)

    def select_day(self, instance):
        """Callback for when a day button is pressed."""
        day = int(instance.text)
        if self.popup:
            self.popup.select_date(datetime.date(self.current_date.year, self.current_date.month, day))

    def go_prev_month(self):
        """Navigates the calendar to the previous month."""
        year, month = self.current_date.year, self.current_date.month
        if month == 1: year, month = year - 1, 12
        else: month -= 1
        self.current_date = datetime.date(year, month, 1)

    def go_next_month(self):
        """Navigates the calendar to the next month."""
        year, month = self.current_date.year, self.current_date.month
        if month == 12: year, month = year + 1, 1
        else: month += 1
        self.current_date = datetime.date(year, month, 1)

class DatePickerPopup(ModalView):
    """A popup that contains a CalendarWidget for date selection."""
    callback = ObjectProperty(None)
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_date = None
        self.ids.calendar_widget.popup = self
    def select_date(self, date):
        """Sets the selected date, calls the callback, and dismisses the popup."""
        self.selected_date = date
        if self.callback: self.callback(self.selected_date)
        self.dismiss()

class MoveCardPopup(ModalView):
    """A popup to select a new list to move a card to."""
    card_widget = ObjectProperty(None)
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(self.populate_lists)

    def populate_lists(self, *args):
        """Fills the popup with buttons for each possible destination list."""
        board = self.card_widget.list_widget.board_widget.board
        source_list_name = self.card_widget.list_widget.list_name
        for list_obj in board.list_objects():
            if list_obj.name != source_list_name:
                btn = Button(text=list_obj.name, size_hint_y=None, height=dp(48))
                btn.bind(on_press=self.move_card_to_list)
                self.ids.list_container.add_widget(btn)

    def move_card_to_list(self, instance):
        """Handles the logic of moving the card to the selected list."""
        dest_list_name = instance.text
        board_widget = self.card_widget.list_widget.board_widget
        source_list_widget = self.card_widget.list_widget
        
        if board_widget.board.move_card(self.card_widget.card_obj, source_list_widget.list_name, dest_list_name):
            App.get_running_app().workspace_manager.save_current_workspace()
            board_widget.populate_lists() # Refresh the board view
            App.get_running_app().show_toast(f"Card moved to '{dest_list_name}'")
        else:
            App.get_running_app().show_toast("Error: Could not move card.")
        self.dismiss()

class CardContextMenu(ModalView):
    """A context menu popup for actions on a single card."""
    card_widget = ObjectProperty(None)
    def on_kv_post(self, base_widget):
        """Dynamically adjusts menu options based on card context."""
        super().on_kv_post(base_widget)
        # If the card is in the "completed" list, disable editing and moving.
        if self.card_widget.is_in_completed_list:
            if self.ids.get('edit_button'):
                self.ids.content_box.remove_widget(self.ids.edit_button)
            if self.ids.get('move_button'):
                self.ids.content_box.remove_widget(self.ids.move_button)

    def edit_card(self):
        self.dismiss()
        self.card_widget.open_edit_popup()
        
    def set_priority(self):
        self.dismiss()
        self.card_widget.set_priority_popup()

    def move_card(self):
        self.dismiss()
        MoveCardPopup(card_widget=self.card_widget).open()
        
    def delete_card(self):
        self.dismiss()
        self.card_widget.delete_card()

class WorkspaceOptionsDialog(ModalView):
    """A dialog showing options for a selected workspace."""
    workspace_name = StringProperty("")
    is_encrypted = BooleanProperty(False)
    def __init__(self, workspace_name, **kwargs):
        super().__init__(**kwargs)
        self.workspace_name = workspace_name
        self.is_encrypted = App.get_running_app().workspace_manager.is_workspace_encrypted(self.workspace_name)

class BoardOptionsDialog(ModalView):
    """A dialog showing options for the current board."""
    board_screen = ObjectProperty(None)
    def open_bin(self):
        """Navigates to the bin screen for the current board."""
        self.dismiss()
        self.board_screen.manager.current = 'bin_screen'
    def delete_board(self):
        """Deletes the current board."""
        self.dismiss()
        workspace = App.get_running_app().workspace_manager.current_workspace()
        # Prevent deleting the last board in a workspace
        if not workspace or len(workspace._boards) <= 1:
            App.get_running_app().show_toast("Cannot delete the last board")
            return
        current_board = workspace.selected_board()
        if current_board:
            workspace._boards.remove(current_board)
            # Adjust selected board index if necessary
            if workspace._selected_board_index >= len(workspace._boards):
                workspace._selected_board_index = len(workspace._boards) - 1
            App.get_running_app().workspace_manager.save_current_workspace()
            App.get_running_app().show_toast(f"Board '{current_board.name}' deleted")
            self.board_screen.load_current_board() # Refresh the board screen

class ListContextMenu(ModalView):
    """A context menu popup for actions on a single list."""
    list_widget = ObjectProperty(None)
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
        """Dynamically changes the text of the 'Set as Completed' button."""
        super().on_kv_post(base_widget)
        board = self.list_widget.board_widget.board
        is_completed = (board.get_completed_list_name() == self.list_widget.list_name)
        if is_completed:
            self.ids.completed_button.text = "Unset as Completed"
            self.ids.completed_button.color = APP_COLORS['accent']
        else:
            self.ids.completed_button.text = "Set as Completed"
            self.ids.completed_button.color = APP_COLORS['text']

    def rename(self):
        self.dismiss()
        self.list_widget.rename_popup()
    def move_to_bin(self):
        self.dismiss()
        self.list_widget.move_to_bin()
    def set_as_completed(self):
        self.dismiss()
        self.list_widget.set_as_completed()

class CardPopup(ModalView):
    """A popup for creating a new card or editing an existing one."""
    title = StringProperty("Create New Card")
    card_obj = ObjectProperty(None, allownone=True) # The card object to edit, if any
    list_widget = ObjectProperty(None)
    callback = ObjectProperty(None)
    deadline_date = ObjectProperty(None, allownone=True)
    
    def on_kv_post(self, base_widget):
        super().on_kv_post(base_widget)
        Clock.schedule_once(self.setup_fields)

    def setup_fields(self, dt=None):
        """Populates the input fields if editing an existing card."""
        if self.card_obj:
            self.ids.card_name_input.text = self.card_obj.name
            self.ids.card_desc_input.text = self.card_obj.description
            if self.card_obj.deadline:
                try:
                    self.deadline_date = datetime.datetime.strptime(self.card_obj.deadline, '%Y-%m-%d %H:%M').date()
                except (ValueError, TypeError):
                    self.deadline_date = None
        self.update_deadline_button_text()

    def update_deadline_button_text(self):
        """Updates the text on the deadline button to show the selected date."""
        if hasattr(self.ids, 'card_deadline_button'):
            if self.deadline_date: 
                self.ids.card_deadline_button.text = self.deadline_date.strftime('%Y-%m-%d')
            else: 
                self.ids.card_deadline_button.text = "Set Deadline"
    
    def open_date_picker(self):
        """Opens the date picker popup."""
        DatePickerPopup(callback=self.set_deadline).open()

    def set_deadline(self, date):
        """Callback function for the date picker."""
        self.deadline_date = date
        self.update_deadline_button_text()

    def save_card(self):
        """Gathers data from inputs and calls the callback to save the card."""
        name = self.ids.card_name_input.text
        description = self.ids.card_desc_input.text
        deadline_str = self.deadline_date.strftime('%Y-%m-%d 00:00') if self.deadline_date else None
        
        # Get priority from slider if new, or keep existing if editing
        if self.card_obj: 
            priority = self.card_obj.priority
        else:
            priority = int(self.ids.priority_slider.value)

        if not name:
            App.get_running_app().show_toast("Card name cannot be empty.")
            return
        if self.callback:
            self.callback(name=name, description=description, deadline=deadline_str, priority=priority, card_to_edit=self.card_obj)
        self.dismiss()

class CardWidget(BoxLayout):
    """The visual representation of a single card in a list."""
    card_obj = ObjectProperty(None)
    list_widget = ObjectProperty(None)
    is_overdue = BooleanProperty(False)
    is_in_completed_list = BooleanProperty(False)
    def open_context_menu(self):
        CardContextMenu(card_widget=self).open()
    def open_edit_popup(self):
        popup = CardPopup(title="Edit Card", card_obj=self.card_obj, list_widget=self, callback=self.list_widget.edit_card_callback)
        popup.open()
    def delete_card(self):
        self.list_widget.delete_card_popup(self.card_obj)
        
    def set_priority_popup(self):
        """Opens a popup to set the card's priority."""
        popup = TextInputPopup(title="Set Priority (0-5)", 
                               hint_text=str(self.card_obj.priority), 
                               callback=self.set_priority_callback)
        popup.open()

    def set_priority_callback(self, value_str):
        """Callback to handle the new priority value."""
        try:
            new_priority = int(value_str)
            if 0 <= new_priority <= 5:
                self.card_obj.priority = new_priority
                App.get_running_app().workspace_manager.save_current_workspace()
                self.list_widget.populate_cards() # Refresh list to show new priority
                App.get_running_app().show_toast("Priority updated.")
            else:
                App.get_running_app().show_toast("Priority must be between 0 and 5.")
        except (ValueError, TypeError):
            App.get_running_app().show_toast("Invalid input. Please enter a number.")


class CreateBoardDialog(ModalView):
    """A simple confirmation dialog to create a new board."""
    board_screen = ObjectProperty(None)
    def create_new_board(self):
        self.dismiss()
        self.board_screen.create_new_board_and_load_it()

class ClickableHeader(BoxLayout):
    """The main header of the board screen, which is clickable."""
    board_screen = ObjectProperty(None)

class ListHeader(BoxLayout):
    """The header for a single list widget."""
    list_widget = ObjectProperty(None)

class WorkspaceCard(ButtonBehavior, BoxLayout):
    """A clickable card representing a single workspace on the main screen."""
    workspace_name = StringProperty('')
    app = ObjectProperty(None)
    last_edited_date = StringProperty('')
    last_edited_time = StringProperty('')
    _long_press_event = None # To handle long press events

    def on_touch_down(self, touch):
        """Schedules a long press event on touch down."""
        if self.collide_point(*touch.pos):
            self.cancel_long_press_event()
            self._long_press_event = Clock.schedule_once(self.long_press_callback, 0.5)
            return super().on_touch_down(touch)
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        """Handles touch up, distinguishing between short and long press."""
        if self.collide_point(*touch.pos):
            if self._long_press_event: # If the long press event hasn't fired yet
                self.cancel_long_press_event()
                self.short_press_callback() # It's a short press
                return True
        self.cancel_long_press_event()
        return super().on_touch_up(touch)

    def cancel_long_press_event(self):
        """Cancels the scheduled long press event."""
        if self._long_press_event:
            self._long_press_event.cancel()
            self._long_press_event = None

    def short_press_callback(self):
        """Action for a short press: open the workspace."""
        self.app.open_workspace(self.workspace_name)

    def long_press_callback(self, _dt):
        """Action for a long press: open the workspace options dialog."""
        self._long_press_event = None
        WorkspaceOptionsDialog(workspace_name=self.workspace_name).open()

class ListWidget(BoxLayout):
    """The visual representation of a single list (column) on the board."""
    list_name = StringProperty('')
    board_widget = ObjectProperty(None)
    is_completed = BooleanProperty(False)
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(lambda dt: self.populate_cards())

    def populate_cards(self):
        """Clears and re-populates the list with its card widgets."""
        cards_container = self.ids.cards_layout
        cards_container.clear_widgets()
        list_obj = next((l for l in self.board_widget.board.list_objects() if l.name == self.list_name), None)
        if not list_obj: return

        is_completed_list = self.board_widget.board.get_completed_list_name() == self.list_name
        for card in list_obj.cards():
            card_widget = CardWidget(
                card_obj=card, 
                list_widget=self, 
                is_overdue=card.is_overdue(),
                is_in_completed_list=is_completed_list
            )
            cards_container.add_widget(card_widget)

    def open_context_menu(self):
        ListContextMenu(list_widget=self).open()

    def set_as_completed(self):
        """Toggles this list's status as the 'completed' list for the board."""
        board = self.board_widget.board
        if board.get_completed_list_name() == self.list_name:
            board.set_completed_list(None) # Unset
            App.get_running_app().show_toast(f"'{self.list_name}' is no longer the completed list.")
        else:
            board.set_completed_list(self.list_name) # Set
            App.get_running_app().show_toast(f"'{self.list_name}' set as the completed list.")
        App.get_running_app().workspace_manager.save_current_workspace()
        self.board_widget.populate_lists() # Refresh board to update visual state

    def rename_popup(self):
        TextInputPopup(title="Rename List", hint_text=self.list_name, callback=self.rename_callback).open()

    def rename_callback(self, new_name):
        """Handles the logic for renaming the list."""
        if not new_name: return
        board = self.board_widget.board
        # Check for name conflicts
        if new_name != self.list_name and board._find_list_by_name(new_name):
            App.get_running_app().show_toast(f"A list named '{new_name}' already exists.")
            return

        list_obj = next((l for l in board.list_objects() if l.name == self.list_name), None)
        if list_obj and list_obj.rename_list(new_name):
            # If this was the completed list, update the name in the board's config
            if board.get_completed_list_name() == self.list_name:
                board.set_completed_list(new_name)
            App.get_running_app().workspace_manager.save_current_workspace()
            self.board_widget.populate_lists()
            App.get_running_app().show_toast(f"List renamed to '{new_name}'")

    def move_to_bin(self):
        """Moves the list and its cards to the bin."""
        if self.board_widget.board.delete_list(self.list_name):
            App.get_running_app().workspace_manager.save_current_workspace()
            self.board_widget.populate_lists()
            App.get_running_app().show_toast(f"'{self.list_name}' moved to bin")

    def add_card_popup(self):
        popup = CardPopup(title="Create New Card", list_widget=self, callback=self.add_card_callback)
        popup.open()

    def add_card_callback(self, name, description, deadline, priority, card_to_edit=None):
        """Callback to create and add a new card to this list."""
        list_obj = next((l for l in self.board_widget.board.list_objects() if l.name == self.list_name), None)
        if list_obj:
            new_card = Card(name=name, description=description, deadline=deadline, priority=priority)
            list_obj.add_card(new_card)
            App.get_running_app().workspace_manager.save_current_workspace()
            self.populate_cards()
            App.get_running_app().show_toast("Card added.")

    def edit_card_callback(self, name, description, deadline, priority, card_to_edit):
        """Callback to save changes to an existing card."""
        if card_to_edit:
            card_to_edit.name = name
            card_to_edit.description = description
            card_to_edit.deadline = deadline
            # Note: Priority is not edited here, but in its own popup.
            App.get_running_app().workspace_manager.save_current_workspace()
            self.populate_cards()
            App.get_running_app().show_toast("Card updated.")

    def delete_card_popup(self, card_obj_to_delete):
        """Shows a confirmation popup before moving a card to the bin."""
        popup = ConfirmationPopup(title="Move Card to Bin?", text=f"Are you sure you want to move '{card_obj_to_delete.name}' to the bin?", callback=lambda: self.delete_card_confirmed(card_obj_to_delete))
        popup.open()

    def delete_card_confirmed(self, card_obj_to_delete):
        """Moves the specified card to the bin."""
        if self.board_widget.board.delete_card(self.list_name, card_obj_to_delete):
            App.get_running_app().workspace_manager.save_current_workspace()
            self.populate_cards()
            App.get_running_app().show_toast(f"Card '{card_obj_to_delete.name}' moved to bin.")
        else:
            App.get_running_app().show_toast("Error: Could not move card to bin.")

class BoardWidget(RelativeLayout):
    """The main widget that holds and displays all the lists for a board."""
    board = ObjectProperty(None)
    def __init__(self, board, **kwargs):
        super().__init__(**kwargs)
        self.board = board
        Clock.schedule_once(lambda dt: self.populate_lists())
    def populate_lists(self):
        """Clears and re-populates the widget with all lists from the board object."""
        lists_container = self.ids.lists_container
        lists_container.clear_widgets()
        # Show a message if the board is empty
        if not self.board.list_objects():
            self.ids.empty_board_label.opacity = 1
            self.ids.scroll_view.opacity = 0
        else:
            self.ids.empty_board_label.opacity = 0
            self.ids.scroll_view.opacity = 1
            for list_obj in self.board.list_objects():
                is_completed_list = self.board.get_completed_list_name() == list_obj.name
                lists_container.add_widget(ListWidget(list_name=list_obj.name, board_widget=self, is_completed=is_completed_list))
    def add_new_list_popup(self):
        TextInputPopup(title="Add New List", hint_text="Enter list name", callback=self.add_new_list_callback).open()
    def add_new_list_callback(self, list_name):
        """Callback to create a new list on the board."""
        if list_name and self.board.create_list(list_name):
            App.get_running_app().workspace_manager.save_current_workspace()
            self.populate_lists()
        elif list_name:
            App.get_running_app().show_toast(f"List '{list_name}' already exists.")

class BinItem(BoxLayout):
    """A widget representing a single deleted item (list or card) in the bin screen."""
    item_name = StringProperty('')
    item_type = StringProperty('')
    bin_screen = ObjectProperty(None)

class WorkspaceScreen(Screen):
    """The main screen of the app, displaying all available workspaces."""
    def on_enter(self, *_):
        """Called when the screen is entered. Refreshes the workspace list."""
        Clock.schedule_once(self.populate_grid)
    def populate_grid(self, *_):
        """Fetches all workspaces and displays them as WorkspaceCard widgets."""
        try:
            self.ids.workspaces_grid.clear_widgets()
            app = App.get_running_app()
            workspaces_data = app.workspace_manager.workspaces()
            # Sort workspaces by last edited date, newest first
            sorted_workspaces = sorted(workspaces_data.items(), key=lambda item: item[1].get('last_edited', ''), reverse=True)
            for name, data in sorted_workspaces:
                iso = data.get("last_edited", datetime.datetime.now().isoformat())
                try:
                    dt = datetime.datetime.fromisoformat(iso)
                    date_str, time_str = dt.strftime('%Y-%m-%d'), dt.strftime('%H:%M')
                except (ValueError, TypeError):
                    date_str, time_str = "Unknown", ""
                self.ids.workspaces_grid.add_widget(WorkspaceCard(workspace_name=name, app=app, last_edited_date=date_str, last_edited_time=time_str))
        except Exception as e:
            print(f"ERROR in populate_grid: {e}\n{traceback.format_exc()}")
            App.get_running_app().show_toast(f"Error: {e}")

class BoardScreen(Screen):
    """The screen that displays a single board with its lists and cards."""
    def on_enter(self, *_):
        """Called when the screen is entered. Loads the currently selected board."""
        self.load_current_board()
    def load_current_board(self, *_):
        """Loads the selected board from the current workspace and displays it."""
        app = App.get_running_app()
        workspace = app.workspace_manager.current_workspace()
        if not workspace:
            self.go_back_to_workspaces()
            return
        board = workspace.selected_board()
        # If no board exists (e.g., in a new workspace), create one.
        if not board:
            workspace.create_board()
            workspace.set_selected_board_by_index(0)
            board = workspace.selected_board()
            app.workspace_manager.save_current_workspace()
        self.ids.board_container.clear_widgets()
        self.ids.board_container.add_widget(BoardWidget(board=board))
        self.update_indicator()

    def load_next_board(self):
        """Switches to the next board in the workspace."""
        workspace = App.get_running_app().workspace_manager.current_workspace()
        if not workspace: return
        current_index = workspace._selected_board_index
        if current_index < len(workspace._boards) - 1:
            workspace.set_selected_board_by_index(current_index + 1)
            self.load_current_board()
        else:
            # If on the last board, prompt to create a new one.
            CreateBoardDialog(board_screen=self).open()

    def load_previous_board(self):
        """Switches to the previous board in the workspace."""
        workspace = App.get_running_app().workspace_manager.current_workspace()
        if not workspace: return
        if workspace._selected_board_index > 0:
            workspace.set_selected_board_by_index(workspace._selected_board_index - 1)
            self.load_current_board()

    def update_indicator(self):
        """Updates the header label to show the current board's name and index."""
        workspace = App.get_running_app().workspace_manager.current_workspace()
        if not workspace or not workspace._boards:
            self.ids.board_indicator_label.text = "No Boards"
            return
        index, board = workspace._selected_board_index, workspace.selected_board()
        self.ids.board_indicator_label.text = f"{board.name} ({index + 1}/{len(workspace._boards)})"

    def create_new_board_and_load_it(self):
        """Creates a new board, saves it, and loads it into view."""
        app = App.get_running_app()
        workspace = app.workspace_manager.current_workspace()
        if not workspace: return
        new_board = workspace.create_board()
        workspace.set_selected_board_by_index(len(workspace._boards) - 1) # Switch to the new board
        app.workspace_manager.save_current_workspace()
        app.show_toast(f"Created '{new_board.name}'")
        self.load_current_board()

    def rename_current_board_popup(self):
        """Opens a popup to rename the current board."""
        workspace = App.get_running_app().workspace_manager.current_workspace()
        if workspace and (current_board := workspace.selected_board()):
            TextInputPopup(title="Rename Board", hint_text=current_board.name, callback=self.rename_current_board_callback).open()

    def rename_current_board_callback(self, new_name):
        """Callback to handle the board renaming logic."""
        workspace, app = App.get_running_app().workspace_manager, App.get_running_app()
        if not new_name or not workspace.current_workspace(): return
        board = workspace.current_workspace().selected_board()
        if not board: return
        if board.rename_board(new_name):
            workspace.save_current_workspace()
            self.update_indicator()
            app.show_toast("Board renamed")

    def add_new_list_to_current_board(self):
        """Triggers the 'add new list' popup on the current BoardWidget."""
        if self.ids.board_container.children:
            current_widget = self.ids.board_container.children[0]
            if isinstance(current_widget, BoardWidget):
                current_widget.add_new_list_popup()

    def open_board_options(self):
        BoardOptionsDialog(board_screen=self).open()

    def go_back_to_workspaces(self):
        """Saves the current workspace and returns to the workspace screen."""
        app = App.get_running_app()
        if app.workspace_manager.current_workspace():
            app.workspace_manager.save_current_workspace()
            app.workspace_manager.close_current_workspace()
        self.manager.transition.direction = 'right'
        self.manager.current = 'workspaces'

class BinScreen(Screen):
    """A screen to view and manage deleted items (lists and cards)."""
    def on_enter(self, *_):
        self.populate_bin()
    def populate_bin(self):
        """Fills the screen with items currently in the board's bin."""
        self.ids.bin_items_grid.clear_widgets()
        workspace = App.get_running_app().workspace_manager.current_workspace()
        if not workspace: return
        board = workspace.selected_board()
        if not board: return
        # Add deleted lists
        for l in board.bin.get_deleted_lists():
            self.ids.bin_items_grid.add_widget(BinItem(item_name=l.name, item_type='list', bin_screen=self))
        # Add deleted cards
        for card_entry in board.bin.get_deleted_cards():
            card = card_entry['card']
            self.ids.bin_items_grid.add_widget(BinItem(item_name=card.name, item_type='card', bin_screen=self))

    def restore_item(self, item_name, item_type):
        """Restores a selected item from the bin back to the board."""
        workspace = App.get_running_app().workspace_manager.current_workspace()
        board = workspace.selected_board() if workspace else None
        if not board: return
        if item_type == 'list':
            restored_list = board.bin.restore_list(item_name)
            if restored_list:
                board.add_list(restored_list)
                App.get_running_app().show_toast(f"List '{item_name}' restored.")
        elif item_type == 'card':
            card_entry = board.bin._find_card_by_name(item_name)
            if not card_entry:
                App.get_running_app().show_toast(f"Error: Card '{item_name}' not found in bin.")
                return
            source_list_name, card_obj = card_entry["source_list"], card_entry["card"]
            source_list_obj = board._find_list_by_name(source_list_name)
            # Restore card to its original list if it exists
            if source_list_obj:
                board.bin.permanently_delete_card(item_name) # Remove from bin
                source_list_obj.add_card(card_obj)
                App.get_running_app().show_toast(f"Card '{card_obj.name}' restored to list '{source_list_name}'.")
            else:
                # If original list is gone, the card cannot be restored.
                board.bin.permanently_delete_card(item_name)
                App.get_running_app().show_toast(f"Original list '{source_list_name}' not found. Card '{item_name}' permanently deleted.")
        App.get_running_app().workspace_manager.save_current_workspace()
        self.populate_bin() # Refresh the bin view

    def delete_item_permanently(self, item_name, item_type):
        """Permanently deletes an item from the bin."""
        workspace = App.get_running_app().workspace_manager.current_workspace()
        if not workspace: return
        board = workspace.selected_board()
        if not board: return
        if item_type == 'list':
            # Find all cards that belonged to this list and delete them too
            cards_to_delete = [entry["card"] for entry in board.bin.get_deleted_cards() if entry["source_list"] == item_name]
            if board.bin.permanently_delete_list(item_name):
                App.get_running_app().show_toast(f"List '{item_name}' permanently deleted.")
                for card in cards_to_delete:
                    board.bin.permanently_delete_card(card.name)
                    App.get_running_app().show_toast(f"List '{item_name}' deleted, also deleting card '{card.name}'.")
                App.get_running_app().workspace_manager.save_current_workspace()
                self.populate_bin()
        elif item_type == 'card':
            if board.bin.permanently_delete_card(item_name):
                App.get_running_app().workspace_manager.save_current_workspace()
                self.populate_bin()
                App.get_running_app().show_toast(f"Card '{item_name}' permanently deleted.")

    def go_back_to_board(self):
        """Navigates back to the main board screen."""
        self.manager.get_screen('board').load_current_board()
        self.manager.current = 'board'

class KanbanApp(App):
    """The main application class."""
    def build(self):
        """Initializes the application, loads resources, and sets up the UI."""
        self.workspace_manager = WorkspaceManager()
        # The notification check has been removed
        try:
            # Register a custom font if available
            LabelBase.register(name="NerdFont", fn_regular="NerdFont.ttf")
        except (OSError, IOError):
            print("NerdFont not found. Using default font.")
            LabelBase.register(name="NerdFont", fn_regular="Roboto") # Fallback font
        Builder.load_file('app.kv') # Load the Kivy language file
        self.sm = ScreenManager(transition=SlideTransition())
        # Set a global background color
        with self.sm.canvas.before:
            Color(rgba=APP_COLORS['background'])
            self.background_rect = Rectangle(size=self.sm.size, pos=self.sm.pos)
        self.sm.bind(pos=self.update_background_rect, size=self.update_background_rect)
        # Add all screens to the screen manager
        self.sm.add_widget(WorkspaceScreen(name='workspaces'))
        self.sm.add_widget(BoardScreen(name='board'))
        self.sm.add_widget(BinScreen(name='bin_screen'))
        return self.sm

    def update_background_rect(self, instance, value):
        """Updates the background rectangle's size and position when the window changes."""
        self.background_rect.pos = instance.pos
        self.background_rect.size = instance.size
    def show_toast(self, text):
        """A helper method to easily show a toast message."""
        try: Toast(text=str(text)).open()
        except Exception as e: print(f"--- FAILED TO CREATE TOAST ---\n{text}\n{e}\n{traceback.format_exc()}")
    def open_workspace(self, workspace_name):
        """Handles the logic for opening a workspace, including password prompts."""
        try:
            if self.workspace_manager.is_workspace_encrypted(workspace_name):
                TextInputPopup(title=f"Password for {workspace_name}", hint_text="Enter password", is_password=True, callback=lambda p: self.open_workspace_callback(workspace_name, p)).open()
            elif self.workspace_manager.open_workspace(workspace_name):
                self.sm.transition.direction = 'left'
                self.sm.current = 'board'
        except Exception as e:
            self.show_toast(f"Error opening: {e}")
            print(traceback.format_exc())
    def open_workspace_callback(self, workspace_name, password):
        """Callback after the user enters a password to open a workspace."""
        try:
            workspace = self.workspace_manager.open_workspace(workspace_name, password=password)
            if workspace and workspace != "password_required":
                self.sm.transition.direction, self.sm.current = 'left', 'board'
            else: self.show_toast("Incorrect password.")
        except Exception as e:
            self.show_toast(f"Error with password: {e}")
            print(traceback.format_exc())
    def create_new_workspace(self):
        """Opens a popup to get a name for a new workspace."""
        TextInputPopup(title="Create Workspace", hint_text="Enter name", callback=self.create_workspace_callback).open()
    def create_workspace_callback(self, name):
        """Callback to create the new workspace."""
        try:
            if not name: self.show_toast("Name cannot be empty."); return
            if self.workspace_manager.create_workspace(name):
                self.show_toast(f"Workspace '{name}' created.")
                self.sm.get_screen('workspaces').populate_grid()
            else: self.show_toast(f"'{name}' already exists.")
        except Exception as e:
            self.show_toast(f"Failed to create: {e}")
            print(traceback.format_exc())
    def delete_workspace(self, workspace_name):
        """Deletes a workspace."""
        try:
            if self.workspace_manager.delete_workspace(workspace_name):
                self.show_toast(f"'{workspace_name}' deleted.")
                self.sm.get_screen('workspaces').populate_grid()
            else: self.show_toast("Error deleting workspace.")
        except Exception as e:
            self.show_toast(f"Failed to delete: {e}")
            print(traceback.format_exc())
    def rename_workspace(self, old_name):
        """Initiates the workspace renaming process, checking for encryption first."""
        try:
            if self.workspace_manager.is_workspace_encrypted(old_name):
                TextInputPopup(title=f"Password for {old_name}", hint_text="Enter password to rename", is_password=True, callback=lambda p: self.rename_password_check_callback(old_name, p)).open()
            else:
                TextInputPopup(title="Rename Workspace", hint_text="Enter new name", callback=lambda n: self.rename_workspace_callback(old_name, n)).open()
        except Exception as e:
            self.show_toast(f"Error renaming: {e}")
            print(traceback.format_exc())
    def rename_password_check_callback(self, old_name, password):
        """Verifies password before allowing rename of an encrypted workspace."""
        try:
            workspace = self.workspace_manager.open_workspace(old_name, password=password)
            if workspace and workspace != "password_required":
                self.workspace_manager.close_current_workspace() # Close it again before renaming
                TextInputPopup(title="Rename Workspace", hint_text="Enter new name", callback=lambda n: self.rename_workspace_callback(old_name, n, password)).open()
            else: self.show_toast("Incorrect password.")
        except Exception as e:
            self.show_toast(f"Password check failed: {e}")
            print(traceback.format_exc())
    _RENAME_IN_PROGRESS = False # A simple lock to prevent race conditions
    def rename_workspace_callback(self, old_name, new_name, password=None):
        """The final callback that performs the workspace renaming."""
        if self._RENAME_IN_PROGRESS: return
        self._RENAME_IN_PROGRESS = True
        try:
            if not new_name: self.show_toast("New name cannot be empty."); return
            if self.workspace_manager.rename_workspace(old_name, new_name, password=password):
                self.show_toast(f"Renamed to '{new_name}'.")
                self.sm.get_screen('workspaces').populate_grid()
            else: self.show_toast(f"Failed to rename.")
        except Exception as e:
            self.show_toast(f"Failed to rename: {e}")
            print(traceback.format_exc())
        finally:
            self._RENAME_IN_PROGRESS = False
    def set_workspace_password(self, workspace_name):
        """Initiates the process to set or change a workspace password."""
        try:
            if self.workspace_manager.is_workspace_encrypted(workspace_name):
                # If already encrypted, ask for current password first
                TextInputPopup(title="Confirm Current Password", hint_text="Enter password", is_password=True, callback=lambda p: self.change_password_confirm_callback(workspace_name, p)).open()
            else:
                # If not encrypted, just ask for the new password
                TextInputPopup(title="Set New Password", hint_text="Enter new password", is_password=True, callback=lambda p: self.set_password_callback(workspace_name, p, is_new=True)).open()
        except Exception as e:
            self.show_toast(f"Error: {e}")
            print(traceback.format_exc())
    def change_password_confirm_callback(self, workspace_name, current_password):
        """Verifies the current password before allowing a change."""
        try:
            workspace = self.workspace_manager.open_workspace(workspace_name, password=current_password)
            if workspace and workspace != "password_required":
                self.workspace_manager.close_current_workspace()
                # Prompt for the new password (blank to remove)
                TextInputPopup(title="Enter New Password", hint_text="Leave blank to remove", is_password=True, callback=lambda n: self.set_password_callback(workspace_name, n, current_password=current_password)).open()
            else: self.show_toast("Incorrect password.")
        except Exception as e:
            self.show_toast(f"Password confirmation failed: {e}")
            print(traceback.format_exc())
    def set_password_callback(self, workspace_name, password, is_new=False, current_password=None):
        """The final callback that actually sets/changes the password on the workspace data."""
        try:
            # Re-open the workspace to modify it
            workspace = self.workspace_manager.open_workspace(workspace_name, password=(current_password if not is_new else None))
            if workspace and workspace != "password_required":
                workspace.set_password(password) # Set new password (or remove if blank)
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
    # Entry point of the application
    KanbanApp().run()