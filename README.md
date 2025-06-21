Kanban Board Application

A desktop task management application built with Python and the Kivy framework. This application provides a Kanban-style interface for organizing tasks into lists and boards within different workspaces. It features local data storage with optional password protection for your workspaces.
Key Features

    Workspace Management: Create, rename, delete, and manage multiple, separate workspaces for different projects.
    Password Protection: Secure your sensitive workspaces with strong, salt-based AES encryption. Only encrypted data is stored on your disk.
    Multiple Boards: Organize your work with multiple boards within each workspace. You can create, rename, and navigate between them.
    Kanban Lists: Within each board, you can create, rename, and manage lists to represent different stages of your workflow.
    Recycle Bin: Deleted lists are moved to a bin, from which they can be restored or permanently deleted, preventing accidental data loss.
    Responsive UI: The user interface is built with Kivy, designed to be simple and responsive for desktop use.
    Local-First Data Storage: All your data is stored locally on your machine in JSON format, ensuring privacy and offline access.

Tech Stack

    Python 3: The core programming language.
    Kivy: Used for the graphical user interface.
    Cryptography: Powers the robust password-based encryption for workspaces.

Setup and Installation

Follow these steps to get the application running on your local machine.

    Prerequisites
        Ensure you have Python 3 installed on your system.

    Clone the Repository
    Bash

# Replace with your repository URL
git clone https://github.com/your-username/your-repository.git
cd your-repository

Create a Virtual Environment (Recommended)
Bash

# For macOS/Linux
python3 -m venv venv
source venv/bin/activate

# For Windows
python -m venv venv
venv\Scripts\activate

Install Dependencies
Install all the required packages using the requirements.txt file.
Bash

pip install -r oop-app/requirements.txt

Run the Application
Execute the main script to launch the app.
Bash

    python oop-app/main.py

How to Use

    Launch the application. You will be greeted with the Workspaces screen.
    Click "+ Add Workspace" to create your first workspace.
    Long-press (or right-click) on a workspace card to see options like renaming, deleting, or adding a password.
    Click on a workspace card to open it. If it's password-protected, you will be prompted to enter the password.
    Inside a workspace, you will see the Board screen. Here you can:
        Use the "+ Add New List" button to create new columns for your tasks.
        Use the arrow buttons in the header to navigate between different boards.
        Click the ellipsis (three dots) icon in the header for board options like renaming or deleting the current board.

Project Structure

    main.py: The main entry point of the application. It contains the Kivy App class, screen management, and UI-facing logic.
    app_classes.py: Contains all the core data classes (WorkspaceManager, Workspace, Board, ListObject, Card, Bin, EncryptionHelper) that model the application's data and business logic.
    app.kv: (Loaded by main.py) Defines the layout, styling, and widget rules for the Kivy user interface.
    requirements.txt: A list of all the Python packages required to run the application.
    workspaces/: A directory that is automatically created to store all workspace data folders.
    workspaces.json: A master file that keeps track of all created workspaces and their paths.