# obs_manager.py
import obsws_python as obs
import time

# Constants for OBS and recording settings (can be moved to a config file)
OBS_HOST = 'localhost'
OBS_PORT = 4455
OBS_PASSWORD = None
RECORDING_INTERVAL = 6
RESTART_DELAY = 1.0


class ObsManager:
    """Manages the connection and commands to OBS Studio."""
    def __init__(self, host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD):
        self.host = host
        self.port = port
        self.password = password
        self.client = None
        self.is_recording = False
        self.recording_timer = None

    def connect(self):
        """Connects to OBS Studio and stops recording if already in progress."""
        try:
            self.client = obs.ReqClient(host=self.host, port=self.port, password=self.password)
            print("Connected to OBS Studio.")
            time.sleep(1)
            self._update_recording_status()
            if self.is_recording:
                print("Stopping initial recording...")
                self.stop_recording()
            return True
        except Exception as e:
            print(f"Failed to connect to OBS Studio: {e}")
            return False

    def _update_recording_status(self):
        """Updates the internal recording status from OBS."""
        if self.client:
            try:
                status = self.client.get_record_status()
                self.is_recording = status.output_active
            except Exception as e:
                print(f"Failed to get recording status: {e}")
                self.is_recording = False

    def _restart_recording(self):
        """Restarts the recording to create a new file."""
        if self.is_recording:  # Double-check before stopping
            try:
                self.client.stop_record()
                time.sleep(0.5)  # Crucial delay
                self.client.start_record()
                print("Recording restarted (new file).")
                self.recording_timer = time.time()  # Reset the timer
            except Exception as e:
                print(f"Failed to restart recording: {e}")

    def start_recording(self):
        """Starts recording."""
        if self.client:
            if not self.is_recording:
                try:
                    self.client.start_record()
                    print("Sent start recording command.")
                    self.is_recording = True
                    self.recording_timer = time.time()
                except Exception as e:
                    print(f"Failed to send start recording command: {e}")
            else:
                print("Already recording. Ignoring START command.")

    def stop_recording(self):
        """Stops recording."""
        if self.client:
            if self.is_recording:
                try:
                    self.client.stop_record()
                    print("Sent stop recording command.")
                    self.is_recording = False
                    self.recording_timer = None
                except Exception as e:
                    print(f"Failed to send stop recording command: {e}")
            else:
                print("Not currently recording. Ignoring STOP command.")
        else:
            print("Not connected to OBS Studio.")
