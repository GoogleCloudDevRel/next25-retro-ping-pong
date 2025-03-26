import os
import time
import glob
import asyncio


class FileManager:
    def __init__(self, segment_complete_event, designated_folder="./videos"):
        self.designated_folder = designated_folder
        self._segment_complete_event = segment_complete_event
        self.processed_files = set()
        self._initialize_processed_files()

        # self.existing_files = set()
        # self.watched_file = None
        # self.watched_file_size = 0
        # self.last_checked_time = 0
        # self.check_interval = 1
        # self._initialize_existing_files()

    def _initialize_processed_files(self):
        if not os.path.exists(self.designated_folder):
            try:
                os.makedirs(self.designated_folder)
                print(f"Created directory: {self.designated_folder}")
            except OSError as e:
                print(f"Error creating directory {self.designated_folder}: {e}")
        else:
            print(f"Directory {self.designated_folder} exists.")

    async def wait_for_completed_file(self):
        print("FileManager: Waiting for recording segment completion signal...")
        await self._segment_complete_event.wait()
        print("FileManager: Received segment completion signal.")
        self._segment_complete_event.clear()

        try:
            all_files = glob.glob(os.path.join(self.designated_folder, "*.mp4"))
            candidate_files = []
            for file_path in all_files:
                abs_path = os.path.abspath(file_path)
                if abs_path not in self.processed_files:
                    try:
                        mtime = os.path.getmtime(abs_path)
                        candidate_files.append((mtime, abs_path))
                    except FileNotFoundError:
                        continue

            if not candidate_files:
                print("FileManager: Signal received, but no new unprocessed files found.")
                return None

            candidate_files.sort(key=lambda x: x[0], reverse=True)
            latest_mtime, completed_file_path = candidate_files[0]

            print(f"FileManager: Identified completed file: {completed_file_path} (mtime: {latest_mtime})")
            self.processed_files.add(completed_file_path)
            return completed_file_path

        except Exception as e:
            print(f"FileManager: Error finding completed file after signal: {e}")
            return None

    # Removed run_monitor and polling logic (monitor_folder)
    # Removed watched_file, watched_file_size, last_checked_time, check_interval attributes

    # def monitor_folder(self):
    #     """Monitors the folder for new files and their completion (polling)."""
    #     completed_file = None
    #     current_files = set(glob.glob(os.path.join(self.designated_folder, "*")))
    #     new_files = current_files - self.existing_files
    #     if new_files:
    #         newest_file = max(new_files, key=os.path.getctime)
    #         print(f"New file detected: {newest_file}")
    #         self.existing_files.add(newest_file)
    #         self.watched_file = newest_file
    #         self.watched_file_size = os.path.getsize(self.watched_file)
    #         self.last_checked_time = time.time()
    #
    #     if self.watched_file:
    #         current_time = time.time()
    #         if current_time - self.last_checked_time >= self.check_interval:
    #             try:
    #                 current_size = os.path.getsize(self.watched_file)
    #                 if current_size == self.watched_file_size:
    #                     print(f"Creating {self.watched_file} is completed.")
    #                     completed_file = self.watched_file
    #                     self.watched_file = None  # Stop watching this file.
    #                     self.watched_file_size = 0
    #                 else:
    #                     self.watched_file_size = current_size
    #             except FileNotFoundError:
    #                 print(f"Watched file {self.watched_file} not found (likely deleted).")
    #                 self.watched_file = None
    #                 self.watched_file_size = 0
    #             self.last_checked_time = time.time()
    #     return completed_file
    #
    # def run_monitor(self):
    #     """Runs the file monitoring loop."""
    #     while True:
    #         self.monitor_folder()
    #         time.sleep(0.5)
