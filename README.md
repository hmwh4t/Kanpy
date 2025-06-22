# Kanpy - Kanban Task Management Application

A feature-rich Kanban board application built with Python and Kivy, designed for personal and team task management with advanced features like encryption, multiple workspaces, and a recycle bin system.

## Features

### 🔐 Security & Privacy
- **Password Protection**: Encrypt workspaces with password-based encryption using PBKDF2 and Fernet
- **Secure Storage**: Encrypted workspaces are stored securely on disk
- **Session Management**: Passwords are only stored in memory during active sessions

### 📋 Task Management
- **Kanban Boards**: Visual task management with customizable lists/columns
- **Card System**: Rich task cards with names, descriptions, deadlines, and priorities
- **Priority Levels**: 5-level priority system with visual indicators
- **Deadline Tracking**: Set deadlines with visual overdue indicators
- **Task Completion**: Designate specific lists as "completed" status

### 🗂️ Organization
- **Multiple Workspaces**: Organize different projects in separate workspaces
- **Multiple Boards**: Each workspace can contain multiple boards
- **Flexible Lists**: Create, rename, and organize lists within boards
- **Drag & Drop**: Move cards between lists seamlessly

### 🗑️ Data Recovery
- **Recycle Bin**: Deleted cards and lists are moved to a recoverable bin
- **Restore Function**: Easily restore accidentally deleted items
- **Permanent Deletion**: Option to permanently remove items when needed

### 💾 Data Management
- **Auto-Save**: Changes are automatically saved to disk
- **JSON Storage**: Human-readable data format when unencrypted
- **Workspace Registry**: Centralized tracking of all workspaces
- **Data Integrity**: Automatic cleanup of invalid workspace entries

## Installation

### Prerequisites
- Python 3.7 or higher
- pip (Python package installer)

### Required Dependencies
```bash
pip install kivy cryptography
```

### Setup
1. Clone or download the project:
```bash
git clone <repository-url>
cd oop-app
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run Kanpy:
```bash
python main.py
```

## Usage

### Getting Started
1. **Launch Kanpy**: Run `python main.py`
2. **Create Workspace**: Click "Create New Workspace" and enter a name
3. **Open Workspace**: Click on a workspace card to open it
4. **Create Lists**: Add columns/lists to organize your tasks
5. **Add Cards**: Create task cards within lists

### Workspace Management
- **Create**: Use the "+" button to create new workspaces
- **Open**: Single-tap workspace cards to open them
- **Options**: Long-press workspace cards for additional options
- **Password Protection**: Set passwords in workspace options
- **Rename/Delete**: Access through workspace options menu

### Board Navigation
- **Multiple Boards**: Use arrow buttons to navigate between boards
- **Board Options**: Access through the header menu (⋮)
- **Create Boards**: Use the "+" option when at the last board
- **Rename Boards**: Long-press the board header

### Task Management
- **Create Cards**: Use the "+" button in any list
- **Edit Cards**: Tap on cards to access context menu
- **Set Priorities**: Use the priority option in card menu (0-5 scale)
- **Set Deadlines**: Use the calendar picker when creating/editing cards
- **Move Cards**: Use the "Move" option in card context menu
- **Complete Tasks**: Move cards to your designated "completed" list

### List Management
- **Create Lists**: Use the "Add List" button on the board
- **Rename Lists**: Long-press list headers
- **Set as Completed**: Designate a list as the "completed" status
- **Delete Lists**: Use the context menu to move lists to bin

### Recycle Bin
- **Access**: Through board options menu
- **View Items**: See all deleted cards and lists
- **Restore**: Bring back accidentally deleted items
- **Permanent Delete**: Remove items permanently when ready

## Project Structure

```
oop-app/
├── app_classes.py          # Core application classes
├── main.py                # Main application and UI logic
├── app.kv                 # Kivy UI layout file
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── workspaces.json        # Workspace registry (auto-generated)
└── workspaces/           # Directory containing workspace data
    ├── workspace1/
    │   └── data.json
    └── workspace2/
        └── data.json
```

## Core Classes

### Data Model Classes
- **`Card`**: Represents individual tasks with properties like name, description, deadline, priority
- **`ListObject`**: Represents columns/lists containing multiple cards
- **`Board`**: Container for multiple lists, represents a single board view
- **`Workspace`**: Container for multiple boards, represents a project workspace
- **`Bin`**: Recycle bin for temporarily storing deleted items

### Management Classes
- **`WorkspaceManager`**: Handles workspace creation, loading, saving, and file system operations
- **`EncryptionHelper`**: Provides password-based encryption/decryption functionality

### UI Classes
- **`KanbanApp`**: Main application class (renamed to KanpyApp in future updates)
- **`WorkspaceScreen`**: Displays available workspaces
- **`BoardScreen`**: Main board view with lists and cards
- **`BinScreen`**: Recycle bin interface
- Various popup and widget classes for UI interactions

## Data Storage

### File Structure
- **Master Config**: `workspaces.json` - Registry of all workspaces
- **Workspace Data**: `workspaces/{name}/data.json` - Individual workspace data
- **Encryption**: Encrypted workspaces store binary data instead of JSON text

### Data Format
Workspaces are stored as JSON with the following structure:
```json
{
  "name": "Workspace Name",
  "last_edited": "2024-01-01T12:00:00",
  "boards": [...],
  "selected_board_index": 0
}
```

## Development

### Architecture
- **MVC Pattern**: Clear separation between data models, views, and controllers
- **Event-Driven**: Kivy's event system handles user interactions
- **Modular Design**: Separate files for data classes and UI logic

### Key Design Patterns
- **Factory Pattern**: Object creation from dictionary data
- **Observer Pattern**: UI updates when data changes
- **Command Pattern**: User actions trigger specific methods

### Extending Kanpy
- **New Features**: Add methods to existing classes or create new widget classes
- **Custom Themes**: Modify `APP_COLORS` dictionary in `main.py`
- **Additional Fields**: Extend `Card` class and update serialization methods

## Security Notes

- Passwords are never stored permanently - only kept in memory during active sessions
- Encryption uses industry-standard PBKDF2 key derivation with 100,000 iterations
- Encrypted data is stored as binary files, unencrypted as readable JSON
- Workspace deletion permanently removes all associated files

## Troubleshooting

### Common Issues
1. **Import Errors**: Ensure all dependencies are installed via pip
2. **Permission Errors**: Check write permissions in application directory
3. **Corrupted Data**: Invalid workspace entries are automatically cleaned up
4. **Font Issues**: Kanpy falls back to default fonts if custom fonts aren't found

### Data Recovery
- Workspaces are automatically backed up in the `workspaces/` directory
- Manual backup: Copy entire `workspaces/` folder and `workspaces.json`
- Recovery: Restore backed up files to application directory
