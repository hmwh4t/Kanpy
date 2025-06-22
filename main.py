import datetime
import traceback
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
from app_classes import WorkspaceManager, Card, Board

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

class ConfirmationPopup(ModalView):
    title = StringProperty("Confirm")
    text = StringProperty("")
    callback = ObjectProperty(None)
    def on_confirm(self):
        if self.callback:
            self.callback()
        self.dismiss()

class CalendarWidget(GridLayout):
    popup = ObjectProperty(None)
    current_date = ObjectProperty(datetime.date.today())
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cols = 7
        self.bind(current_date=self.update_calendar)
        Clock.schedule_once(lambda dt: self.update_calendar())

    def update_calendar(self, *args):
        self.clear_widgets()
        year = self.current_date.year
        month = self.current_date.month
        today = datetime.date.today()
        for day in ['S', 'M', 'T', 'W', 'T', 'F', 'S']:
            self.add_widget(Label(text=day, size_hint_y=None, height=dp(30), color=APP_COLORS['text_secondary']))
        first_day_of_month = datetime.date(year, month, 1).weekday()
        start_day_index = (first_day_of_month + 1) % 7
        num_days_in_month = (datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)).day if month < 12 else 31
        for _ in range(start_day_index):
            self.add_widget(Label(text=""))
        for day_num in range(1, num_days_in_month + 1):
            day_date = datetime.date(year, month, day_num)
            day_button = Button(text=str(day_num), on_press=self.select_day, background_color=(0, 0, 0, 0))
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
        day = int(instance.text)
        if self.popup:
            self.popup.select_date(datetime.date(self.current_date.year, self.current_date.month, day))

    def go_prev_month(self):
        year, month = self.current_date.year, self.current_date.month
        if month == 1: year, month = year - 1, 12
        else: month -= 1
        self.current_date = datetime.date(year, month, 1)

    def go_next_month(self):
        year, month = self.current_date.year, self.current_date.month
        if month == 12: year, month = year + 1, 1
        else: month += 1
        self.current_date = datetime.date(year, month, 1)

class DatePickerPopup(ModalView):
    callback = ObjectProperty(None)
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_date = None
        self.ids.calendar_widget.popup = self
    def select_date(self, date):
        self.selected_date = date
        if self.callback: self.callback(self.selected_date)
        self.dismiss()

class MoveCardPopup(ModalView):
    card_widget = ObjectProperty(None)
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(self.populate_lists)

    def populate_lists(self, *args):
        board = self.card_widget.list_widget.board_widget.board
        source_list_name = self.card_widget.list_widget.list_name
        for list_obj in board.list_objects():
            if list_obj.name != source_list_name:
                btn = Button(text=list_obj.name, size_hint_y=None, height=dp(48))
                btn.bind(on_press=self.move_card_to_list)
                self.ids.list_container.add_widget(btn)

    def move_card_to_list(self, instance):
        dest_list_name = instance.text
        board_widget = self.card_widget.list_widget.board_widget
        source_list_widget = self.card_widget.list_widget
        
        if board_widget.board.move_card(self.card_widget.card_obj, source_list_widget.list_name, dest_list_name):
            App.get_running_app().workspace_manager.save_current_workspace()
            board_widget.populate_lists()
            App.get_running_app().show_toast(f"Card moved to '{dest_list_name}'")
        else:
            App.get_running_app().show_toast("Error: Could not move card.")
        self.dismiss()

class CardContextMenu(ModalView):
    card_widget = ObjectProperty(None)
    def on_kv_post(self, base_widget):
        super().on_kv_post(base_widget)
        if self.card_widget.is_in_completed_list:
            if self.ids.get('edit_button'):
                self.ids.content_box.remove_widget(self.ids.edit_button)
            if self.ids.get('move_button'):
                self.ids.content_box.remove_widget(self.ids.move_button)

    def edit_card(self):
        self.dismiss()
        self.card_widget.open_edit_popup()
    def move_card(self):
        self.dismiss()
        MoveCardPopup(card_widget=self.card_widget).open()
    def delete_card(self):
        self.dismiss()
        self.card_widget.delete_card()

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

    # THIS IS THE FIX: Use the standard Kivy __init__ so that properties
    # like 'list_widget' are properly assigned before on_kv_post is called.
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
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
    title = StringProperty("Create New Card")
    card_obj = ObjectProperty(None, allownone=True)
    list_widget = ObjectProperty(None)
    callback = ObjectProperty(None)
    deadline_date = ObjectProperty(None, allownone=True)
    
    def on_kv_post(self, base_widget):
        super().on_kv_post(base_widget)
        # Use Clock.schedule_once to delay until ids are available
        Clock.schedule_once(self.setup_fields)

    def setup_fields(self, dt=None):
        """Setup fields after KV widgets are created."""
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
        # Check if the button exists before trying to access it
        if hasattr(self.ids, 'card_deadline_button'):
            if self.deadline_date: 
                self.ids.card_deadline_button.text = self.deadline_date.strftime('%Y-%m-%d')
            else: 
                self.ids.card_deadline_button.text = "Set Deadline"
    def open_date_picker(self):
        DatePickerPopup(callback=self.set_deadline).open()
    def set_deadline(self, date):
        self.deadline_date = date
        self.update_deadline_button_text()
    def save_card(self):
        name = self.ids.card_name_input.text
        description = self.ids.card_desc_input.text
        deadline_str = self.deadline_date.strftime('%Y-%m-%d 00:00') if self.deadline_date else None
        if not name:
            App.get_running_app().show_toast("Card name cannot be empty.")
            return
        if self.callback:
            self.callback(name=name, description=description, deadline=deadline_str, card_to_edit=self.card_obj)
        self.dismiss()

class CardWidget(BoxLayout):
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

class CreateBoardDialog(ModalView):
    board_screen = ObjectProperty(None)
    def create_new_board(self):
        self.dismiss()
        self.board_screen.create_new_board_and_load_it()

class ClickableHeader(BoxLayout):
    board_screen = ObjectProperty(None)

class ListHeader(BoxLayout):
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
            return super().on_touch_down(touch)
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
        WorkspaceOptionsDialog(workspace_name=self.workspace_name).open()

class ListWidget(BoxLayout):
    list_name = StringProperty('')
    board_widget = ObjectProperty(None)
    is_completed = BooleanProperty(False)
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(lambda dt: self.populate_cards())

    def populate_cards(self):
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
        board = self.board_widget.board
        if board.get_completed_list_name() == self.list_name:
            board.set_completed_list(None)
            App.get_running_app().show_toast(f"'{self.list_name}' is no longer the completed list.")
        else:
            board.set_completed_list(self.list_name)
            App.get_running_app().show_toast(f"'{self.list_name}' set as the completed list.")
        App.get_running_app().workspace_manager.save_current_workspace()
        self.board_widget.populate_lists()

    def rename_popup(self):
        TextInputPopup(title="Rename List", hint_text=self.list_name, callback=self.rename_callback).open()

    def rename_callback(self, new_name):
        if not new_name: return
        board = self.board_widget.board
        if new_name != self.list_name and board._find_list_by_name(new_name):
            App.get_running_app().show_toast(f"A list named '{new_name}' already exists.")
            return

        list_obj = next((l for l in board.list_objects() if l.name == self.list_name), None)
        if list_obj and list_obj.rename_list(new_name):
            if board.get_completed_list_name() == self.list_name:
                board.set_completed_list(new_name)
            App.get_running_app().workspace_manager.save_current_workspace()
            self.board_widget.populate_lists()
            App.get_running_app().show_toast(f"List renamed to '{new_name}'")

    def move_to_bin(self):
        if self.board_widget.board.delete_list(self.list_name):
            App.get_running_app().workspace_manager.save_current_workspace()
            self.board_widget.populate_lists()
            App.get_running_app().show_toast(f"'{self.list_name}' moved to bin")

    def add_card_popup(self):
        popup = CardPopup(title="Create New Card", list_widget=self, callback=self.add_card_callback)
        popup.open()

    def add_card_callback(self, name, description, deadline, card_to_edit=None):
        list_obj = next((l for l in self.board_widget.board.list_objects() if l.name == self.list_name), None)
        if list_obj:
            new_card = Card(name=name, description=description, deadline=deadline if deadline else None)
            list_obj.add_card(new_card)
            App.get_running_app().workspace_manager.save_current_workspace()
            self.populate_cards()
            App.get_running_app().show_toast("Card added.")

    def edit_card_callback(self, name, description, deadline, card_to_edit):
        if card_to_edit:
            card_to_edit.name = name
            card_to_edit.description = description
            card_to_edit.deadline = deadline if deadline else None
            App.get_running_app().workspace_manager.save_current_workspace()
            self.populate_cards()
            App.get_running_app().show_toast("Card updated.")

    def delete_card_popup(self, card_obj_to_delete):
        popup = ConfirmationPopup(title="Move Card to Bin?", text=f"Are you sure you want to move '{card_obj_to_delete.name}' to the bin?", callback=lambda: self.delete_card_confirmed(card_obj_to_delete))
        popup.open()

    def delete_card_confirmed(self, card_obj_to_delete):
        if self.board_widget.board.delete_card(self.list_name, card_obj_to_delete):
            App.get_running_app().workspace_manager.save_current_workspace()
            self.populate_cards()
            App.get_running_app().show_toast(f"Card '{card_obj_to_delete.name}' moved to bin.")
        else:
            App.get_running_app().show_toast("Error: Could not move card to bin.")

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
                is_completed_list = self.board.get_completed_list_name() == list_obj.name
                lists_container.add_widget(ListWidget(list_name=list_obj.name, board_widget=self, is_completed=is_completed_list))
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
                    date_str, time_str = dt.strftime('%Y-%m-%d'), dt.strftime('%H:%M')
                except (ValueError, TypeError):
                    date_str, time_str = "Unknown", ""
                self.ids.workspaces_grid.add_widget(WorkspaceCard(workspace_name=name, app=app, last_edited_date=date_str, last_edited_time=time_str))
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
            workspace.create_board()
            workspace.set_selected_board_by_index(0)
            board = workspace.selected_board()
            app.workspace_manager.save_current_workspace()
        self.ids.board_container.clear_widgets()
        self.ids.board_container.add_widget(BoardWidget(board=board))
        self.update_indicator()

    def load_next_board(self):
        workspace = App.get_running_app().workspace_manager.current_workspace()
        if not workspace: return
        current_index = workspace._selected_board_index
        if current_index < len(workspace._boards) - 1:
            workspace.set_selected_board_by_index(current_index + 1)
            self.load_current_board()
        else:
            CreateBoardDialog(board_screen=self).open()

    def load_previous_board(self):
        workspace = App.get_running_app().workspace_manager.current_workspace()
        if not workspace: return
        if workspace._selected_board_index > 0:
            workspace.set_selected_board_by_index(workspace._selected_board_index - 1)
            self.load_current_board()

    def update_indicator(self):
        workspace = App.get_running_app().workspace_manager.current_workspace()
        if not workspace or not workspace._boards:
            self.ids.board_indicator_label.text = "No Boards"
            return
        index, board = workspace._selected_board_index, workspace.selected_board()
        self.ids.board_indicator_label.text = f"{board.name} ({index + 1}/{len(workspace._boards)})"

    def create_new_board_and_load_it(self):
        app = App.get_running_app()
        workspace = app.workspace_manager.current_workspace()
        if not workspace: return
        new_board = workspace.create_board()
        workspace.set_selected_board_by_index(len(workspace._boards) - 1)
        app.workspace_manager.save_current_workspace()
        app.show_toast(f"Created '{new_board.name}'")
        self.load_current_board()

    def rename_current_board_popup(self):
        workspace = App.get_running_app().workspace_manager.current_workspace()
        if workspace and (current_board := workspace.selected_board()):
            TextInputPopup(title="Rename Board", hint_text=current_board.name, callback=self.rename_current_board_callback).open()

    def rename_current_board_callback(self, new_name):
        workspace, app = App.get_running_app().workspace_manager, App.get_running_app()
        if not new_name or not workspace.current_workspace(): return
        board = workspace.current_workspace().selected_board()
        if not board: return
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
            self.ids.bin_items_grid.add_widget(BinItem(item_name=l.name, item_type='list', bin_screen=self))
        for card_entry in board.bin.get_deleted_cards():
            card = card_entry['card']
            self.ids.bin_items_grid.add_widget(BinItem(item_name=card.name, item_type='card', bin_screen=self))

    def restore_item(self, item_name, item_type):
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
            if source_list_obj:
                board.bin.permanently_delete_card(item_name)
                source_list_obj.add_card(card_obj)
                App.get_running_app().show_toast(f"Card '{card_obj.name}' restored to list '{source_list_name}'.")
            else:
                board.bin.permanently_delete_card(item_name)
                App.get_running_app().show_toast(f"Original list '{source_list_name}' not found. Card '{item_name}' permanently deleted.")
        App.get_running_app().workspace_manager.save_current_workspace()
        self.populate_bin()

    def delete_item_permanently(self, item_name, item_type):
        workspace = App.get_running_app().workspace_manager.current_workspace()
        if not workspace: return
        board = workspace.selected_board()
        if not board: return
        if item_type == 'list':
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
        self.manager.get_screen('board').load_current_board()
        self.manager.current = 'board'

class KanbanApp(App):
    def build(self):
        self.workspace_manager = WorkspaceManager()
        try:
            LabelBase.register(name="NerdFont", fn_regular="NerdFont.ttf")
        except (OSError, IOError):
            print("NerdFont not found. Using default font.")
            LabelBase.register(name="NerdFont", fn_regular="Roboto")
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
        try: Toast(text=str(text)).open()
        except Exception as e: print(f"--- FAILED TO CREATE TOAST ---\n{text}\n{e}\n{traceback.format_exc()}")
    def open_workspace(self, workspace_name):
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
        try:
            workspace = self.workspace_manager.open_workspace(workspace_name, password=password)
            if workspace and workspace != "password_required":
                self.sm.transition.direction, self.sm.current = 'left', 'board'
            else: self.show_toast("Incorrect password.")
        except Exception as e:
            self.show_toast(f"Error with password: {e}")
            print(traceback.format_exc())
    def create_new_workspace(self):
        TextInputPopup(title="Create Workspace", hint_text="Enter name", callback=self.create_workspace_callback).open()
    def create_workspace_callback(self, name):
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
        try:
            if self.workspace_manager.delete_workspace(workspace_name):
                self.show_toast(f"'{workspace_name}' deleted.")
                self.sm.get_screen('workspaces').populate_grid()
            else: self.show_toast("Error deleting workspace.")
        except Exception as e:
            self.show_toast(f"Failed to delete: {e}")
            print(traceback.format_exc())
    def rename_workspace(self, old_name):
        try:
            if self.workspace_manager.is_workspace_encrypted(old_name):
                TextInputPopup(title=f"Password for {old_name}", hint_text="Enter password to rename", is_password=True, callback=lambda p: self.rename_password_check_callback(old_name, p)).open()
            else:
                TextInputPopup(title="Rename Workspace", hint_text="Enter new name", callback=lambda n: self.rename_workspace_callback(old_name, n)).open()
        except Exception as e:
            self.show_toast(f"Error renaming: {e}")
            print(traceback.format_exc())
    def rename_password_check_callback(self, old_name, password):
        try:
            workspace = self.workspace_manager.open_workspace(old_name, password=password)
            if workspace and workspace != "password_required":
                self.workspace_manager.close_current_workspace()
                TextInputPopup(title="Rename Workspace", hint_text="Enter new name", callback=lambda n: self.rename_workspace_callback(old_name, n, password)).open()
            else: self.show_toast("Incorrect password.")
        except Exception as e:
            self.show_toast(f"Password check failed: {e}")
            print(traceback.format_exc())
    _RENAME_IN_PROGRESS = False
    def rename_workspace_callback(self, old_name, new_name, password=None):
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
        try:
            if self.workspace_manager.is_workspace_encrypted(workspace_name):
                TextInputPopup(title="Confirm Current Password", hint_text="Enter password", is_password=True, callback=lambda p: self.change_password_confirm_callback(workspace_name, p)).open()
            else:
                TextInputPopup(title="Set New Password", hint_text="Enter new password", is_password=True, callback=lambda p: self.set_password_callback(workspace_name, p, is_new=True)).open()
        except Exception as e:
            self.show_toast(f"Error: {e}")
            print(traceback.format_exc())
    def change_password_confirm_callback(self, workspace_name, current_password):
        try:
            workspace = self.workspace_manager.open_workspace(workspace_name, password=current_password)
            if workspace and workspace != "password_required":
                self.workspace_manager.close_current_workspace()
                TextInputPopup(title="Enter New Password", hint_text="Leave blank to remove", is_password=True, callback=lambda n: self.set_password_callback(workspace_name, n, current_password=current_password)).open()
            else: self.show_toast("Incorrect password.")
        except Exception as e:
            self.show_toast(f"Password confirmation failed: {e}")
            print(traceback.format_exc())
    def set_password_callback(self, workspace_name, password, is_new=False, current_password=None):
        try:
            workspace = self.workspace_manager.open_workspace(workspace_name, password=(current_password if not is_new else None))
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