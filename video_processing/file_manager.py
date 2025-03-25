# file_manager.py
import os
import time
import glob


class FileManager:
    def __init__(self, designated_folder="./videos"):
        self.designated_folder = designated_folder
        self.existing_files = set()
        self.watched_file = None
        self.watched_file_size = 0
        self.last_checked_time = 0
        self.check_interval = 1
        self._initialize_existing_files()

    def _initialize_existing_files(self):
        """Loads existing files in the designated folder into a set."""
        if not os.path.exists(self.designated_folder):
            try:
                os.makedirs(self.designated_folder)
            except OSError as e:
                print(f"Error creating directory {self.designated_folder}: {e}")
                return

        for file in glob.glob(os.path.join(self.designated_folder, "*")):
            self.existing_files.add(file)

    def monitor_folder(self):
        """Monitors the folder for new files and their completion (polling)."""
        completed_file = None
        current_files = set(glob.glob(os.path.join(self.designated_folder, "*")))
        new_files = current_files - self.existing_files
        if new_files:
            newest_file = max(new_files, key=os.path.getctime)
            print(f"New file detected: {newest_file}")
            self.existing_files.add(newest_file)
            self.watched_file = newest_file
            self.watched_file_size = os.path.getsize(self.watched_file)
            self.last_checked_time = time.time()

        if self.watched_file:
            current_time = time.time()
            if current_time - self.last_checked_time >= self.check_interval:
                try:
                    current_size = os.path.getsize(self.watched_file)
                    if current_size == self.watched_file_size:
                        print(f"Creating {self.watched_file} is completed.")
                        completed_file = self.watched_file
                        self.watched_file = None  # Stop watching this file.
                        self.watched_file_size = 0
                    else:
                        self.watched_file_size = current_size
                except FileNotFoundError:
                    print(f"Watched file {self.watched_file} not found (likely deleted).")
                    self.watched_file = None
                    self.watched_file_size = 0
                self.last_checked_time = time.time()
        return completed_file

    def run_monitor(self):
        """Runs the file monitoring loop."""
        while True:
            self.monitor_folder()
            time.sleep(0.5)
