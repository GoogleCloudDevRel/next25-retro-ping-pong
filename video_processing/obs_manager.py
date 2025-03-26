import obsws_python as obs
import time
import asyncio

# Constants for OBS and recording settings (can be moved to a config file)
OBS_HOST = 'localhost'
OBS_PORT = 4455
OBS_PASSWORD = None
RESTART_DELAY = 2.0


class ObsManager:
    """
    Manages the connection and commands to OBS Studio asynchronously.
    Runs blocking obsws_python calls in an executor thread pool.
    """
    def __init__(self, segment_complete_event, host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD):
        self.host = host
        self.port = port
        self.password = password
        self._segment_complete_event = segment_complete_event
        self.client = None
        self._loop = None
        self._lock = asyncio.Lock()

        self._is_recording_state = False
        self._recording_timer_state = None
        self._last_started_timestamp = 0

    @property
    def is_recording(self):
        return self._is_recording_state

    @property
    def recording_timer(self):
        return self._recording_timer_state

    @property
    def is_connected(self):
        return self.client is not None

    async def async_connect(self):
        """Connects to OBS Studio and stops recording if already in progress."""
        self._loop = asyncio.get_running_loop()
        try:
            print("Attempting to connect to OBS...")
            self.client = await self._loop.run_in_executor(
                None, self._blocking_connect
            )
            print("Connected to OBS Studio.")
            await asyncio.sleep(0.5)
            await self.async_update_recording_status()
            if self._is_recording_state:
                print("OBS was recording initially, attempting to stop...")
                await self.async_stop_recording()
            return True
        except Exception as e:
            print(f"Failed to connect to OBS Studio: {e}")
            self.client = None
            return False

    def _blocking_connect(self):
        """Synchronous part of the connection logic."""
        client = obs.ReqClient(host=self.host, port=self.port, password=self.password, timeout=5)
        return client

    async def async_disconnect(self):
        """Disconnects from OBS asynchronously."""
        if self.client and self._loop:
            print("Disconnecting from OBS...")
            async with self._lock:
                try:
                    await self._loop.run_in_executor(None, setattr, self, 'client', None)
                    print("OBS Cclient reference cleared.")
                except Exception as e:
                    print(f"Error during OBS disconnect simulation: {e}")
                finally:
                    self.client = None

    async def async_update_recording_status(self):
        if self.client and self._loop:
            try:
                status = await self._loop.run_in_executor(
                    None, self.client.get_record_status,
                )
                async with self._lock:
                    self._is_recording_state = status.output_active
            except Exception as e:
                print(f"Failed to get recording status: {e}")
                async with self._lock:
                    self._is_recording_state = False

    async def async_start_recording(self):
        if not self.client or not self._loop:
            print("Cannot start recording: Not connected to OBS.")
            return

        async with self._lock:
            if not self._is_recording_state:
                try:
                    print("Sending start recording command (async)...")
                    await self._loop.run_in_executor(
                        None, self.client.start_record
                    )
                    self._is_recording_state = True
                    self._recording_timer_state = time.time()
                    self._last_started_timestamp = self._recording_timer_state
                    print("OBS recording started.")
                except Exception as e:
                    print(f"Failed to send start recording command: {e}")
            else:
                print("Already recording. Ignoring START command.")

    async def async_stop_recording(self):
        """Stops recording asynchronously."""
        if not self.client or not self._loop:
            print("Cannot stop recording: Not connected to OBS.")
            return

        async with self._lock: # Prevent race conditions with start/restart
            if self._is_recording_state:
                try:
                    print("Sending stop recording command (async)...")
                    await self._loop.run_in_executor(
                        None, self.client.stop_record
                    )
                    self._is_recording_state = False
                    self._recording_timer_state = None
                    print("OBS recording stopped.")
                    self._segment_complete_event.set()
                except Exception as e:
                    print(f"Failed to send stop recording command: {e}")
                    # State remains True if exception occurred, may need manual check
            else:
                print("Not currently recording. Ignoring STOP command.")

    async def async_restart_recording(self):
        """Restarts the recording asynchronously to create a new file."""
        if not self.client or not self._loop:
            print("Cannot restart recording: Not connected.")
            return

        async with self._lock:
            if self._is_recording_state:
                try:
                    print("Restarting recording (async)...")
                    await self._loop.run_in_executor(
                        None, self._blocking_restart_sequence
                    )
                    self._recording_timer_state = time.time()
                    print("OBS recording restarted (new file).")
                    self._segment_complete_event.set()
                except Exception as e:
                    print(f"Failed to restart recording: {e}")
                    asyncio.create_task(self.async_update_recording_status())
            else:
                print("Cannot restart: Not currently recording.")

    def _blocking_restart_sequence(self):
        """The synchronous sequence for restarting recording. Runs in executor."""
        self.client.stop_record()
        time.sleep(RESTART_DELAY)
        self.client.start_record()
