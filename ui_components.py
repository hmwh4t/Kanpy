"""
UI Components for the Kanban App

This module provides reusable UI components and dialogs for the Kanban application.
It includes:
- Toast notifications
- Text input dialogs
- Confirmation dialogs  
- Calendar widgets
- Date picker popups

All components follow consistent styling using APP_COLORS from config.
"""

import datetime

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.properties import ObjectProperty, StringProperty, BooleanProperty
from kivy.clock import Clock
from kivy.uix.modalview import ModalView
from kivy.metrics import dp

from config import APP_COLORS, TOAST_DURATION


class Toast(ModalView):
    """
    A small, temporary popup message (similar to Android's Toast).
    
    Automatically dismisses after TOAST_DURATION seconds.
    Used for brief status messages and feedback to users.
    
    Args:
        text (str): The message to display in the toast
    """
    text = StringProperty('')
    
    def __init__(self, text, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self._schedule_dismiss()
    
    def _schedule_dismiss(self):
        """Schedule the toast to automatically dismiss after the configured duration."""
        Clock.schedule_once(lambda dt: self.dismiss(), TOAST_DURATION)


class TextInputPopup(ModalView):
    """
    A modal dialog for collecting text input from the user.
    
    Features:
    - Customizable title and hint text
    - Optional password mode for sensitive input
    - Callback function called with the entered text
    
    Args:
        title (str): Dialog title text
        hint_text (str): Placeholder text for the input field
        callback (callable): Function to call with the entered text
        is_password (bool): Whether to hide the input text
    """
    title = StringProperty("Enter Value")
    hint_text = StringProperty("")
    callback = ObjectProperty(None)
    is_password = BooleanProperty(False)
    
    def on_submit(self, text_input):
        """Handle text input submission."""
        if self.callback:
            self.callback(text_input)
        self.dismiss()


class ConfirmationPopup(ModalView):
    """
    A modal dialog for user confirmation actions.
    
    Displays a title, message text, and Cancel/Confirm buttons.
    The callback is only executed if the user confirms the action.
    
    Args:
        title (str): Dialog title text
        text (str): Main message text
        callback (callable): Function to call if user confirms
    """
    title = StringProperty("Confirm")
    text = StringProperty("")
    callback = ObjectProperty(None)
    
    def on_confirm(self):
        """Execute the callback function when user confirms the action."""
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
        self._update_popup_label()
        self.clear_widgets()
        
        year, month = self.current_date.year, self.current_date.month
        today = datetime.date.today()
        
        self._add_day_headers()
        self._add_empty_day_slots(year, month)
        self._add_day_buttons(year, month, today)

    def _update_popup_label(self):
        """Update the month/year label in the popup if it exists."""
        if self.popup:
            self.popup.ids.month_year_label.text = self.current_date.strftime('%B %Y')

    def _add_day_headers(self):
        """Add the day header labels (S, M, T, W, T, F, S)."""
        for day in ['S', 'M', 'T', 'W', 'T', 'F', 'S']:
            label = Label(
                text=day, 
                size_hint_y=None, 
                height=dp(30), 
                color=APP_COLORS['text_secondary']
            )
            self.add_widget(label)

    def _add_empty_day_slots(self, year, month):
        """Add empty labels for days before the 1st of the month."""
        first_day_of_month = datetime.date(year, month, 1).weekday()
        start_day_index = (first_day_of_month + 1) % 7
        
        for _ in range(start_day_index):
            self.add_widget(Label(text=""))

    def _add_day_buttons(self, year, month, today):
        """Add a button for each day of the month."""
        num_days = self._get_days_in_month(year, month)
        
        for day_num in range(1, num_days + 1):
            day_date = datetime.date(year, month, day_num)
            day_button = self._create_day_button(day_num, day_date, today)
            self.add_widget(day_button)

    def _get_days_in_month(self, year, month):
        """Get the number of days in the given month."""
        if month < 12:
            next_month = datetime.date(year, month + 1, 1)
        else:
            next_month = datetime.date(year + 1, 1, 1)
        return (next_month - datetime.timedelta(days=1)).day

    def _create_day_button(self, day_num, day_date, today):
        """Create a styled button for a specific day."""
        button = Button(
            text=str(day_num), 
            on_press=self.select_day, 
            background_color=(0, 0, 0, 0)
        )
        
        if day_date < today:
            button.disabled = True
            button.disabled_color = APP_COLORS['text_secondary']
        elif day_date == today:
            button.disabled = True
            button.disabled_color = APP_COLORS['primary']
            button.bold = True
        else:
            button.disabled = False
            button.color = APP_COLORS['text']
            
        return button

    def select_day(self, instance):
        """Callback for when a day button is pressed."""
        day = int(instance.text)
        if self.popup:
            selected_date = datetime.date(
                self.current_date.year, 
                self.current_date.month, 
                day
            )
            self.popup.select_date(selected_date)

    def go_prev_month(self):
        """Navigates the calendar to the previous month."""
        year, month = self.current_date.year, self.current_date.month
        if month == 1:
            year, month = year - 1, 12
        else:
            month -= 1
        self.current_date = datetime.date(year, month, 1)

    def go_next_month(self):
        """Navigates the calendar to the next month."""
        year, month = self.current_date.year, self.current_date.month
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
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
        if self.callback:
            self.callback(self.selected_date)
        self.dismiss()
