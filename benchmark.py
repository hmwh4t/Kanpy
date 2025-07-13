import time
import os
import shutil
import random
import string
import sys

# Ensure the app_classes module can be found
try:
    from app_classes import WorkspaceManager, Card
except ImportError:
    print("Error: Could not import from 'app_classes.py'.")
    print("Please make sure 'benchmark.py' is in the same directory as 'app_classes.py'.")
    sys.exit(1)

# --- Benchmark Configuration ---

# Directory and file names for the benchmark run to avoid conflicts
BENCHMARK_DIR = "benchmark_workspaces"
CONFIG_FILE = "benchmark_workspaces.json"

# Number of items to generate
# WARNING: These numbers will generate a very large amount of data and may take a long time to run.
# Total data size could be several gigabytes.
NUM_WORKSPACES = 1000
NUM_BOARDS_PER_WORKSPACE = 100
NUM_LISTS_PER_BOARD = 10
NUM_CARDS_PER_LIST = 10

# Configuration for generated content
TEXT_LENGTH = 100
PASSWORD = "a_strong_benchmark_password_!@#$%"

# --- Helper Functions ---

def generate_random_text(length: int) -> str:
    """Generates a random string of a given length."""
    letters = string.ascii_letters + string.digits + " "
    return ''.join(random.choice(letters) for _ in range(length))

def cleanup():
    """Removes all files and directories created during the benchmark."""
    print("\nCleaning up benchmark files...")
    try:
        if os.path.exists(BENCHMARK_DIR):
            shutil.rmtree(BENCHMARK_DIR)
            print(f"Removed directory: {BENCHMARK_DIR}")
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
            print(f"Removed file: {CONFIG_FILE}")
        print("Cleanup complete.")
    except OSError as e:
        print(f"Error during cleanup: {e}")

def print_results(total_time: float):
    """Prints a formatted summary of the benchmark results."""
    total_boards = NUM_WORKSPACES * NUM_BOARDS_PER_WORKSPACE
    total_lists = total_boards * NUM_LISTS_PER_BOARD
    total_cards = total_lists * NUM_CARDS_PER_LIST

    print("\n" + "="*40)
    print("--- BENCHMARK RESULTS ---")
    print("="*40)
    print(f"Workspaces created and encrypted: {NUM_WORKSPACES}")
    print(f"Total Boards generated:           {total_boards:,}")
    print(f"Total Lists generated:            {total_lists:,}")
    print(f"Total Cards generated:            {total_cards:,}")
    print("-" * 40)
    print(f"Total time taken:                 {total_time:.2f} seconds")
    if NUM_WORKSPACES > 0:
        avg_time_per_workspace = total_time / NUM_WORKSPACES
        print(f"Average time per workspace:       {avg_time_per_workspace:.4f} seconds")
    print("="*40)

# --- Main Benchmark Logic ---

def run_benchmark():
    """
    Executes the main benchmark process: creating, populating,
    encrypting, and saving all the specified workspaces.
    """
    # Initialize a WorkspaceManager pointed at the benchmark directory
    wm = WorkspaceManager(config_path=CONFIG_FILE, workspaces_dir=BENCHMARK_DIR)
    
    print("Starting benchmark...")
    print(f"Will create {NUM_WORKSPACES} encrypted workspaces.")
    print("This may take a significant amount of time and disk space.")
    
    start_time = time.time()

    for i in range(NUM_WORKSPACES):
        workspace_name = f"BenchmarkWorkspace_{i+1:04d}"
        
        # 1. Create the workspace structure
        wm.create_workspace(workspace_name)
        
        # 2. Open it to start populating data
        # We open with no password, then set it on the object to mark it for encryption on save.
        workspace = wm.open_workspace(workspace_name, password=None)
        if not workspace:
            print(f"Error: Failed to create or open {workspace_name}. Aborting.")
            return

        workspace.set_password(PASSWORD)
        
        # Clear the single default board to add our own batch
        workspace._boards = []

        # 3. Populate the workspace with boards, lists, and cards
        for j in range(NUM_BOARDS_PER_WORKSPACE):
            board = workspace.create_board() # create_board handles naming
            board.name = generate_random_text(TEXT_LENGTH)
            
            for k in range(NUM_LISTS_PER_BOARD):
                # We need a unique name for each list
                list_name = generate_random_text(TEXT_LENGTH - 10) + f"_l{k}"
                list_obj = board.create_list(name=list_name)
                if not list_obj: continue # Skip if list creation fails (e.g., name collision)

                for _ in range(NUM_CARDS_PER_LIST):
                    card = Card(
                        name=generate_random_text(TEXT_LENGTH),
                        description=generate_random_text(TEXT_LENGTH)
                    )
                    list_obj.add_card(card)
        
        # 4. Save the fully populated workspace. This is the step where
        # serialization and encryption actually occur.
        wm.save_current_workspace()
        
        # 5. Close the workspace to free memory before the next iteration
        wm.close_current_workspace()
        
        # Provide progress feedback
        print(f"  > Completed {workspace_name} ({i+1}/{NUM_WORKSPACES})")

    end_time = time.time()
    
    print_results(end_time - start_time)


if __name__ == '__main__':
    # Clean up any previous benchmark runs before starting
    cleanup()
    
    try:
        run_benchmark()
    except Exception as e:
        print(f"\nAn unexpected error occurred during the benchmark: {e}")
    finally:
        # Prompt the user before deleting all the generated files
        input("\nBenchmark finished. Press Enter to clean up the generated files...")
        cleanup()
