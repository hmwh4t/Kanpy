# =====================================================
# IMPORTS
# =====================================================

# Standard library imports
import datetime
import traceback

# Kivy framework imports
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.modalview import ModalView
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import ObjectProperty, StringProperty, BooleanProperty
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.utils import get_color_from_hex
from kivy.graphics import Color, Rectangle, Line
from kivy.lang import Builder
from kivy.core.text import LabelBase
from kivy.animation import Animation
from kivy.core.window import Window

# Local application imports
from app_classes import WorkspaceManager, Card, Board
from ui_components import Toast, TextInputPopup, ConfirmationPopup, CalendarWidget, DatePickerPopup
from config import APP_COLORS, LONG_PRESS_DURATION, KV_FILE_PATH, DEFAULT_FONT_NAME, FALLBACK_FONT_NAME, FONT_FILE_PATH

# =====================================================
# UTILITY FUNCTIONS
# =====================================================

def get_app():
    """Get the running app instance."""
    return App.get_running_app()

def get_workspace_manager():
    """Get the workspace manager from the app."""
    return get_app().workspace_manager

def get_drag_manager():
    """Get the drag drop manager from the app."""
    return get_app().drag_drop_manager

def show_toast(message):
    """Show a toast message."""
    get_app().show_toast(message)

def save_current_workspace():
    """Save the current workspace."""
    get_workspace_manager().save_current_workspace()

# =====================================================
# DRAG AND DROP SYSTEM
# =====================================================

class DragDropManager:
    """
    Manages drag and drop operations for cards in the Kanban app.
    
    Handles:
    - Starting and ending drag operations
    - Creating visual drag ghosts
    - Auto-scrolling during drag
    - Drop location detection
    - Visual drop indicators
    """
    
    def __init__(self):
        # Drag state tracking
        self.is_dragging = False
        self.dragged_card = None
        self.dragged_card_widget = None
        self.drag_ghost = None
        
        # Original position tracking for cancellation
        self.original_parent = None
        self.original_list_widget = None
        
        # Visual feedback
        self.drop_indicator = None
        self.indicator_parent = None
        
        # Auto-scroll functionality
        self.scroll_trigger = None

        # Bind to mouse movement for ghost positioning
        Window.bind(mouse_pos=self.on_mouse_move)

    def on_mouse_move(self, window, pos):
        """Update ghost position when mouse moves."""
        if self.is_dragging and self.drag_ghost:
            offset_x = self.drag_ghost.width / 2
            offset_y = self.drag_ghost.height / 2
            self.drag_ghost.pos = (pos[0] - offset_x, pos[1] - offset_y)
            self._update_drop_indicators(pos)

    def start_drag(self, card_widget):
        """Initiates a drag operation and starts the auto-scroll check."""
        if self.is_dragging:
            return False
            
        self.is_dragging = True
        self.dragged_card = card_widget.card_obj
        self.dragged_card_widget = card_widget
        self.original_parent = card_widget.parent
        self.original_list_widget = card_widget.list_widget

        card_widget.opacity = 0.3
        self._create_drag_ghost(card_widget)
        self._disable_scrolling()
        
        # Start the auto-scroll check, running 60 times per second
        self.scroll_trigger = Clock.schedule_interval(self._check_auto_scroll, 1/60.0)
        return True

    def _create_drag_ghost(self, card_widget):
        """Creates a visual copy of the card that follows the cursor."""
        app = get_app()
        current_screen = app.sm.current_screen

        ghost = Label(
            text=card_widget.card_obj.name,
            size_hint=(None, None),
            size=card_widget.size,
            color=APP_COLORS['white'],
            bold=True
        )
        with ghost.canvas.before:
            Color(rgba=get_color_from_hex("#3B82F6"))
            ghost.bg_rect = Rectangle(pos=ghost.pos, size=ghost.size, radius=[dp(4)])
        
        def update_graphics(instance, value):
            instance.bg_rect.pos = instance.pos
            instance.bg_rect.size = instance.size
        
        ghost.bind(pos=update_graphics, size=update_graphics)
        current_screen.add_widget(ghost)
        self.drag_ghost = ghost
        return True

    def _update_drop_indicators(self, touch_pos):
        """Updates the visual drop indicators based on cursor position."""
        drop_location = self._find_drop_location(touch_pos)
        if drop_location:
            self._show_drop_indicator(drop_location)
        else:
            self._clear_drop_indicator()

    def _find_drop_location(self, touch_pos):
        """FIXED: Finds the correct list, including the last one, to drop the card."""
        app = App.get_running_app()
        board_screen = app.sm.get_screen('board')
        
        if not board_screen.ids.board_container.children: return None
        board_widget = board_screen.ids.board_container.children[0]
        if not isinstance(board_widget, BoardWidget): return None
            
        lists_container = board_widget.ids.lists_container
        
        # Debug: Print touch position
        print(f"Touch pos: {touch_pos}")
        
        # Check each list widget directly with window coordinates
        for list_widget in lists_container.children:
            if not isinstance(list_widget, ListWidget): continue
            
            # Convert window coordinates to this specific list widget's coordinates
            local_pos_in_list = list_widget.to_widget(*touch_pos)
            
            # Use collide_point with the correctly transformed coordinates
            if list_widget.collide_point(*local_pos_in_list):
                print(f"Found collision with list: {list_widget.list_name}")
                return self._find_card_drop_position(touch_pos, list_widget)
        
        print("No collision found with any list")
        return None

    def _find_card_drop_position(self, touch_pos, list_widget):
        """Finds the exact index within a list's cards_layout to drop the card."""
        cards_layout = list_widget.ids.cards_layout
        local_pos = cards_layout.to_widget(*touch_pos)
        
        print(f"Cards layout local pos: {local_pos}")
        
        children = [child for child in cards_layout.children if isinstance(child, CardWidget)]
        children.reverse()

        if not children:
            print(f"Empty list, inserting at index 0")
            return { 'list_widget': list_widget, 'cards_layout': cards_layout, 'index': 0, 'local_y': cards_layout.height }
        
        for i, card_widget in enumerate(children):
            if card_widget == self.dragged_card_widget: continue
            
            if local_pos[1] > (card_widget.y + card_widget.height / 2):
                print(f"Inserting at index {i}")
                return { 'list_widget': list_widget, 'cards_layout': cards_layout, 'index': i, 'local_y': card_widget.top }
        
        last_card = children[-1]
        print(f"Inserting at end, index {len(children)}")
        return { 'list_widget': list_widget, 'cards_layout': cards_layout, 'index': len(children), 'local_y': last_card.y }

    def _show_drop_indicator(self, drop_location):
        """Shows a line indicator by adding it directly to the target list."""
        target_layout = drop_location['cards_layout']
        
        if not self.drop_indicator:
            self.drop_indicator = Widget(size_hint=(None, None), size=(0, dp(2)))
            with self.drop_indicator.canvas:
                Color(rgba=get_color_from_hex("#3B82F6"))
                self.drop_indicator.rect = Rectangle(pos=self.drop_indicator.pos, size=self.drop_indicator.size)
        
        if self.drop_indicator.parent != target_layout:
            if self.drop_indicator.parent:
                self.drop_indicator.parent.remove_widget(self.drop_indicator)
            target_layout.add_widget(self.drop_indicator)

        self.drop_indicator.width = target_layout.width - dp(10)
        self.drop_indicator.pos = (dp(5), drop_location['local_y'] - dp(1))
        
        self.drop_indicator.rect.pos = self.drop_indicator.pos
        self.drop_indicator.rect.size = self.drop_indicator.size
        self.drop_indicator.opacity = 1

    def _clear_drop_indicator(self):
        """Removes the drop indicator."""
        if self.drop_indicator and self.drop_indicator.parent:
            self.drop_indicator.parent.remove_widget(self.drop_indicator)
            self.drop_indicator.parent = None

    def end_drag(self, touch_pos):
        """Ends the drag operation and stops the auto-scroll check."""
        print(f"=== END DRAG at position: {touch_pos} ===")
        drop_location = self._find_drop_location(touch_pos)
        print(f"Drop location found: {drop_location is not None}")
        if drop_location:
            print(f"Calling _perform_drop with location: {drop_location}")
            self._perform_drop(drop_location)
        else:
            print("No drop location found, not performing drop")
        self._cleanup_drag()
        return True
        
    def _perform_drop(self, drop_location):
        """Moves the card data and refreshes the UI."""
        app = App.get_running_app()
        target_list_widget = drop_location['list_widget']
        target_index = drop_location['index']
        
        # Debug output
        print(f"Drop attempt: list='{target_list_widget.list_name}', index={target_index}")
        print(f"Original list: {self.original_list_widget.list_name}")
        print(f"Card name: {self.dragged_card.name}")
        
        if target_list_widget == self.original_list_widget and target_index == self.original_parent.children.index(self.dragged_card_widget):
            print("Same position, skipping drop")
            return

        workspace = app.workspace_manager.current_workspace()
        board = workspace.selected_board()
        source_list_obj = next(l for l in board.list_objects() if l.name == self.original_list_widget.list_name)
        target_list_obj = next(l for l in board.list_objects() if l.name == target_list_widget.list_name)

        print(f"Source list cards before: {[c.name for c in source_list_obj._cards]}")
        print(f"Target list cards before: {[c.name for c in target_list_obj._cards]}")

        # Store original index BEFORE removing the card
        original_data_index = -1
        if self.dragged_card in source_list_obj._cards:
            original_data_index = source_list_obj._cards.index(self.dragged_card)
            source_list_obj._cards.remove(self.dragged_card)
            print(f"Removed card from source list at index {original_data_index}")
        
        if source_list_obj == target_list_obj:
            # If moving down in the same list, adjust target index
            if original_data_index != -1 and original_data_index < target_index:
                 target_index -= 1
                 print(f"Adjusted target index to {target_index} for same-list move")

        target_list_obj._cards.insert(target_index, self.dragged_card)
        print(f"Inserted card at index {target_index}")
        print(f"Target list cards after: {[c.name for c in target_list_obj._cards]}")
        
        # Save and refresh
        app.workspace_manager.save_current_workspace()
        print("Saved workspace")
        
        self.original_list_widget.populate_cards()
        if target_list_widget != self.original_list_widget:
            target_list_widget.populate_cards()
        print("Refreshed UI")
        
        app.show_toast(f"Card moved to '{target_list_widget.list_name}'")

    def _cleanup_drag(self):
        """Cleans up visuals, resets state, and stops the auto-scroll check."""
        if self.scroll_trigger:
            self.scroll_trigger.cancel()
            self.scroll_trigger = None

        if self.dragged_card_widget:
            self.dragged_card_widget.opacity = 1.0
        
        if self.drag_ghost and self.drag_ghost.parent:
            self.drag_ghost.parent.remove_widget(self.drag_ghost)
        
        self._clear_drop_indicator()
        self._enable_scrolling()
        
        self.is_dragging = False
        self.dragged_card = None
        self.dragged_card_widget = None
        self.drag_ghost = None
        self.original_parent = None
        self.original_list_widget = None

    def _find_scroll_view(self, widget):
        """Helper to find a ScrollView in a widget's children."""
        for child in widget.children:
            if isinstance(child, ScrollView):
                return child
        return None
    
    # --- NEW AND IMPROVED AUTO-SCROLL LOGIC ---
    
    def _check_auto_scroll(self, dt):
        """NEW: Checks if the cursor is near an edge to trigger scrolling."""
        if not self.is_dragging:
            return

        x, y = Window.mouse_pos
        app = App.get_running_app()
        board_screen = app.sm.get_screen('board')
        if not board_screen.ids.board_container.children: return
        board_widget = board_screen.ids.board_container.children[0]
        if not isinstance(board_widget, BoardWidget): return

        self._auto_scroll_horizontal(x, board_widget)
        self._auto_scroll_vertical(x, y, board_widget)

    def _auto_scroll_horizontal(self, x, board_widget):
        """NEW: Scrolls the main board left or right."""
        h_scroll_view = board_widget.ids.scroll_view
        scroll_edge_threshold = dp(50)
        scroll_speed = 15.0

        if x < h_scroll_view.x + scroll_edge_threshold:
            h_scroll_view.scroll_x = max(0, h_scroll_view.scroll_x - scroll_speed / h_scroll_view.width)
        elif x > h_scroll_view.right - scroll_edge_threshold:
            h_scroll_view.scroll_x = min(1, h_scroll_view.scroll_x + scroll_speed / h_scroll_view.width)

    def _auto_scroll_vertical(self, x, y, board_widget):
        """NEW: Scrolls a list up or down."""
        lists_container = board_widget.ids.lists_container
        local_pos_in_container = lists_container.to_widget(x, y)
        scroll_edge_threshold = dp(50)
        scroll_speed = 15.0

        for list_widget in lists_container.children:
            if list_widget.collide_point(*local_pos_in_container):
                v_scroll_view = self._find_scroll_view(list_widget)
                if v_scroll_view:
                    if y > v_scroll_view.top - scroll_edge_threshold:
                        v_scroll_view.scroll_y = min(1, v_scroll_view.scroll_y + scroll_speed / v_scroll_view.height)
                    elif y < v_scroll_view.y + scroll_edge_threshold:
                        v_scroll_view.scroll_y = max(0, v_scroll_view.scroll_y - scroll_speed / v_scroll_view.height)
                break
    
    def _disable_scrolling(self):
        """Disables scrolling to prevent conflicts during drag."""
        app = App.get_running_app()
        board_screen = app.sm.get_screen('board')
        if board_screen.ids.board_container.children:
            board_widget = board_screen.ids.board_container.children[0]
            if isinstance(board_widget, BoardWidget):
                board_widget.ids.scroll_view.do_scroll_x = False
                lists_container = board_widget.ids.lists_container
                for list_widget in lists_container.children:
                    if isinstance(list_widget, ListWidget):
                        list_scroll_view = self._find_scroll_view(list_widget)
                        if list_scroll_view:
                            list_scroll_view.do_scroll_y = False

    def _enable_scrolling(self):
        """Re-enables scrolling after drag operation is finished."""
        app = App.get_running_app()
        board_screen = app.sm.get_screen('board')
        if board_screen.ids.board_container.children:
            board_widget = board_screen.ids.board_container.children[0]
            if isinstance(board_widget, BoardWidget):
                board_widget.ids.scroll_view.do_scroll_x = True
                lists_container = board_widget.ids.lists_container
                for list_widget in lists_container.children:
                    if isinstance(list_widget, ListWidget):
                        list_scroll_view = self._find_scroll_view(list_widget)
                        if list_scroll_view:
                            list_scroll_view.do_scroll_y = True

class DragDropIndicator(Widget):
    """A blue line widget that indicates where a card will be dropped."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class CardContextMenu(ModalView):
    """A context menu popup for actions on a single card."""
    card_widget = ObjectProperty(None)

    def on_kv_post(self, base_widget):
        """Dynamically adjusts menu options based on card context."""
        super().on_kv_post(base_widget)
        # If the card is in the "completed" list, disable editing.
        if self.card_widget.is_in_completed_list:
            if self.ids.get('edit_button'):
                self.ids.content_box.remove_widget(self.ids.edit_button)
        
        # Remove move button since we now have drag and drop
        if self.ids.get('move_button'):
            self.ids.content_box.remove_widget(self.ids.move_button)

    def edit_card(self):
        self.dismiss()
        self.card_widget.open_edit_popup()

    def set_priority(self):
        self.dismiss()
        self.card_widget.set_priority_popup()

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
    card_obj = ObjectProperty(None, allownone=True)  # The card object to edit, if any
    list_widget = ObjectProperty(None)
    callback = ObjectProperty(None)
    deadline_date = ObjectProperty(None, allownone=True)

    def on_kv_post(self, base_widget):
        super().on_kv_post(base_widget)
        Clock.schedule_once(self.setup_fields)

    def setup_fields(self, dt=None):
        """Populates the input fields if editing an existing card."""
        if self.card_obj:
            self._populate_existing_card_data()
        self.update_deadline_button_text()

    def _populate_existing_card_data(self):
        """Helper method to populate fields with existing card data."""
        self.ids.card_name_input.text = self.card_obj.name
        self.ids.card_desc_input.text = self.card_obj.description

        if self.card_obj.deadline:
            self.deadline_date = self._parse_deadline_string(self.card_obj.deadline)

    def _parse_deadline_string(self, deadline_str):
        """Parse deadline string and return date object, or None if invalid."""
        try:
            return datetime.datetime.strptime(deadline_str, '%Y-%m-%d %H:%M').date()
        except (ValueError, TypeError):
            return None

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
        card_data = self._gather_card_data()

        if not card_data['name']:
            App.get_running_app().show_toast("Card name cannot be empty.")
            return

        if self.callback:
            self.callback(**card_data, card_to_edit=self.card_obj)
        self.dismiss()

    def _gather_card_data(self):
        """Gather all card data from the form inputs."""
        name = self.ids.card_name_input.text
        description = self.ids.card_desc_input.text
        deadline_str = self.deadline_date.strftime('%Y-%m-%d 00:00') if self.deadline_date else None

        # Get priority from slider if new, or keep existing if editing
        if self.card_obj:
            priority = self.card_obj.priority
        else:
            priority = int(self.ids.priority_slider.value)

        return {
            'name': name,
            'description': description,
            'deadline': deadline_str,
            'priority': priority
        }


class CardWidget(BoxLayout):
    """
    The visual representation of a single card in a list.
    
    Features:
    - Drag and drop functionality
    - Long press for context menu
    - Visual states for overdue and completed cards
    - Touch handling for interactions
    """
    card_obj = ObjectProperty(None)
    list_widget = ObjectProperty(None)
    is_overdue = BooleanProperty(False)
    is_in_completed_list = BooleanProperty(False)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Touch state tracking for drag detection
        self._touch_start_pos = None
        self._is_potential_drag = False
        self._long_press_event = None

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            drag_manager = get_drag_manager()
            if drag_manager.is_dragging:
                return False
                
            self._touch_start_pos = touch.pos
            self._is_potential_drag = True
            
            self._long_press_event = Clock.schedule_once(
                lambda dt: self._show_context_menu_if_not_dragging(), 0.5)
            
            touch.grab(self)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self and self._is_potential_drag:
            if self._touch_start_pos:
                dx = touch.pos[0] - self._touch_start_pos[0]
                dy = touch.pos[1] - self._touch_start_pos[1]
                distance = (dx**2 + dy**2)**0.5
                
                # If moved more than the threshold, start the drag
                if distance > dp(10):
                    self._cancel_long_press()
                    self._start_drag() # No longer needs to pass touch
                    return True
            
            # --- THIS BLOCK WAS REMOVED ---
            # The window's on_mouse_move now handles all position updates.
            # No need to manually update the position from here.
            
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            
            drag_manager = App.get_running_app().drag_drop_manager
            
            if drag_manager.is_dragging and drag_manager.dragged_card_widget == self:
                # Use current mouse position instead of touch.pos which can be incorrect
                current_mouse_pos = Window.mouse_pos
                print(f"Using mouse position instead of touch.pos: {current_mouse_pos}")
                drag_manager.end_drag(current_mouse_pos)
                self._reset_touch_state()
                return True
            
            if self._is_potential_drag and self._touch_start_pos:
                distance = ((touch.pos[0] - self._touch_start_pos[0])**2 + 
                          (touch.pos[1] - self._touch_start_pos[1])**2)**0.5
                if distance <= dp(10):
                    self._cancel_long_press()
                    Clock.schedule_once(lambda dt: self.open_context_menu(), 0.1)
            
            self._reset_touch_state()
            return True
            
        return super().on_touch_up(touch)

    def _start_drag(self):
        """FIXED: Initiates drag operation for this card without passing touch.
        
        Note: Cards can now be moved from/to any list including completed lists.
        Previously there may have been a restriction preventing cards from being 
        moved out of completed lists, but this has been removed to allow full
        drag-and-drop functionality.
        """
        drag_manager = App.get_running_app().drag_drop_manager
        if drag_manager.start_drag(self):
            # The call to update_drag_position was removed from here.
            # The on_mouse_move event will handle the ghost's position.
            self._is_potential_drag = False

    def _show_context_menu_if_not_dragging(self):
        """Shows context menu if we're not in the middle of a drag."""
        if self._is_potential_drag:
            self.open_context_menu()
            self._reset_touch_state()

    def _cancel_long_press(self):
        """Cancels the scheduled long press event."""
        if self._long_press_event:
            self._long_press_event.cancel()
            self._long_press_event = None

    def _reset_touch_state(self):
        """Resets all touch-related state variables."""
        self._touch_start_pos = None
        self._is_potential_drag = False
        self._cancel_long_press()

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
                self.list_widget.populate_cards()
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
    """
    A clickable card representing a single workspace on the main screen.
    
    Features:
    - Short tap to open workspace
    - Long press for options menu
    - Displays workspace name and last edited time
    """
    workspace_name = StringProperty('')
    app = ObjectProperty(None)
    last_edited_date = StringProperty('')
    last_edited_time = StringProperty('')
    _long_press_event = None  # To handle long press events

    def on_touch_down(self, touch):
        """Schedules a long press event on touch down."""
        if self.collide_point(*touch.pos):
            self.cancel_long_press_event()
            self._long_press_event = Clock.schedule_once(self.long_press_callback, LONG_PRESS_DURATION)
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

    def open_rearrange_dialog(self):
        """Opens the dialog to rearrange lists if there's more than one."""
        workspace = App.get_running_app().workspace_manager.current_workspace()
        if workspace:
            board = workspace.selected_board()
            if board and len(board.list_objects()) > 1:
                popup = RearrangeListsPopup(board=board, board_screen=self)
                popup.open()
            elif board:
                App.get_running_app().show_toast("Not enough lists to rearrange.")

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


class DraggableListItem(BoxLayout):
    """A list item that can be dragged to reorder."""
    list_name = StringProperty('')
    is_dragged = BooleanProperty(False)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.grab(self)
            self.is_dragged = True
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            parent = self.parent
            my_index_in_children = parent.children.index(self)

            # Find which widget we are hovering over
            for i, child in enumerate(parent.children):
                if child is self:
                    continue
                if child.collide_point(*touch.pos):
                    if i != my_index_in_children:
                        parent.remove_widget(self)
                        parent.add_widget(self, index=i)
                    break
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self.is_dragged = False
            return True
        return super().on_touch_up(touch)


class RearrangeListsPopup(ModalView):
    """A popup for rearranging the order of lists on a board."""
    board = ObjectProperty(None)
    board_screen = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(self.populate_lists)

    def populate_lists(self, *args):
        self.ids.lists_container.clear_widgets()
        if self.board:
            for list_obj in self.board.list_objects():
                item = DraggableListItem(list_name=list_obj.name)
                self.ids.lists_container.add_widget(item)

    def save_order(self):
        if not self.board:
            self.dismiss()
            return

        new_order_widgets = self.ids.lists_container.children[::-1]
        new_order_names = [widget.list_name for widget in new_order_widgets]

        original_lists_map = {lst.name: lst for lst in self.board.list_objects()}

        reordered_list_objects = [original_lists_map[name] for name in new_order_names if name in original_lists_map]

        self.board._list_objects = reordered_list_objects

        App.get_running_app().workspace_manager.save_current_workspace()
        self.board_screen.load_current_board()
        self.dismiss()


class KanbanApp(App):
    """
    The main application class for the Kanban app.
    
    Handles:
    - Application initialization
    - Font setup
    - UI setup
    - Workspace and drag-drop management
    """

    def build(self):
        """Initialize the application, load resources, and set up the UI."""
        self.workspace_manager = WorkspaceManager()
        self.drag_drop_manager = DragDropManager()

        self._setup_fonts()
        self._setup_ui()

        return self.sm

    def _setup_fonts(self):
        """Setup custom fonts with fallback to default if unavailable."""
        try:
            LabelBase.register(name=DEFAULT_FONT_NAME, fn_regular=FONT_FILE_PATH)
        except (OSError, IOError):
            print(f"{DEFAULT_FONT_NAME} not found. Using default font.")
            LabelBase.register(name=DEFAULT_FONT_NAME, fn_regular=FALLBACK_FONT_NAME)

    def _setup_ui(self):
        """Setup the user interface and screen manager."""
        Builder.load_file(KV_FILE_PATH)
        self.sm = ScreenManager(transition=SlideTransition())

        self._setup_background()
        self._add_screens()

    def _setup_background(self):
        """Setup the global background color."""
        with self.sm.canvas.before:
            Color(rgba=APP_COLORS['background'])
            self.background_rect = Rectangle(size=self.sm.size, pos=self.sm.pos)
        self.sm.bind(pos=self.update_background_rect, size=self.update_background_rect)

    def _add_screens(self):
        """Add all screens to the screen manager."""
        screens = [
            WorkspaceScreen(name='workspaces'),
            BoardScreen(name='board'),
            BinScreen(name='bin_screen')
        ]
        for screen in screens:
            self.sm.add_widget(screen)

    def update_background_rect(self, instance, value):
        """Updates the background rectangle's size and position when the window changes."""
        self.background_rect.pos = instance.pos
        self.background_rect.size = instance.size

    def show_toast(self, text):
        """A helper method to easily show a toast message."""
        try:
            Toast(text=str(text)).open()
        except Exception as e:
            print(f"--- FAILED TO CREATE TOAST ---\n{text}\n{e}\n{traceback.format_exc()}")

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