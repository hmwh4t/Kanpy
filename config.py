# ===========================
# Configuration Constants for the Kanban App
# ===========================
# This file contains all application-wide constants and configuration values

from kivy.utils import get_color_from_hex

# ===========================
# UI CONSTANTS
# ===========================

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

# UI Layout Constants
CARD_SPACING = 8
LIST_SPACING = 10
LIST_WIDTH = "280dp"
CARD_BORDER_RADIUS = 8
LIST_BORDER_RADIUS = 12

# ===========================
# APPLICATION CONSTANTS
# ===========================

# Font Configuration
DEFAULT_FONT_NAME = "NerdFont"
FALLBACK_FONT_NAME = "Roboto"
FONT_FILE_PATH = "NerdFont.ttf"

# File and Directory Names
WORKSPACES_CONFIG_FILE = "workspaces.json"
WORKSPACES_DIRECTORY = "workspaces"
WORKSPACE_DATA_FILE = "data.json"
KV_FILE_PATH = "app.kv"

# Long Press Configuration
LONG_PRESS_DURATION = 0.5  # seconds

# Toast Configuration
TOAST_DURATION = 1.5  # seconds

# ===========================
# VALIDATION CONSTANTS
# ===========================

# Priority limits
MIN_PRIORITY = 0
MAX_PRIORITY = 5

# Input validation
MAX_CARD_NAME_LENGTH = 100
MAX_LIST_NAME_LENGTH = 50
MAX_BOARD_NAME_LENGTH = 50
MAX_WORKSPACE_NAME_LENGTH = 50

# ===========================
# ENCRYPTION CONSTANTS
# ===========================

# Constants for key derivation function (KDF) - from EncryptionHelper
SALT_LENGTH = 16  # Size of the salt in bytes
KEY_LENGTH = 32   # Desired key length in bytes
PBKDF2_ITERATIONS = 100000  # Number of iterations for PBKDF2, for security

# ===========================
# DATE & TIME CONSTANTS
# ===========================

# Date format strings
DATE_FORMAT = '%Y-%m-%d'
DATETIME_FORMAT = '%Y-%m-%d %H:%M'
DEADLINE_FORMAT = '%Y-%m-%d 00:00'
ISO_FORMAT = '%Y-%m-%dT%H:%M:%S'
