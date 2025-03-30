import os
import errno
import stat

PIPE_G2V_PATH = "/tmp/paddlebounce_pipe_g2v"
PIPE_V2G_PATH = "/tmp/paddlebounce_pipe_v2g"


class PipeManager:
    def __init__(self, write_pipe_path, read_pipe_path):
        self.write_path = write_pipe_path
        self.read_path = read_pipe_path
        self.write_fd = None
        self.read_fd = None
        self.read_buffer = b""
        print(f"PipeManager initialized to write to '{write_pipe_path}' and read from '{read_pipe_path}'.")

    def _ensure_pipe_exists(self, path):
        try:
            if not os.path.exists(path):
                os.mkfifo(path)
                print(f"Pipe created: {path}")
            elif not stat.S_ISFIFO(os.stat(path).st_mode):
                print(f"🚨 Error: Path {path} exists but is not a FIFO. Please remove it manually.")
                return False
        except OSError as e:
            if e.errno != errno.EEXIST:
                print(f"🚨 Error creating or checking pipe {path}: {e}")
                return False
        except Exception as e:
            print(f"🚨 Unexpected error ensuring pipe exists {path}: {e}")
            return False
        return True

    def setup_pipes(self):
        """읽기/쓰기 파이프를 설정합니다. 쓰기 파이프는 블로킹 방식으로 엽니다."""
        print(f"Setting up pipes: Write='{self.write_path}', Read='{self.read_path}'")

        if not self._ensure_pipe_exists(self.write_path):
            return False
        if not self._ensure_pipe_exists(self.read_path):
            return False

        try:
            print(f"Attempting to open read pipe: {self.read_path} (O_RDONLY | O_NONBLOCK)")
            self.read_fd = os.open(self.read_path, os.O_RDONLY | os.O_NONBLOCK)
            print(f"Read pipe opened successfully: {self.read_path} (fd: {self.read_fd})")
        except Exception as e:
            print(f"🚨 Error opening read pipe {self.read_path}: {e}")
            self.close_pipes()
            return False

        try:
            print(f"Attempting to open write pipe: {self.write_path} (O_WRONLY) - This may block...")
            self.write_fd = os.open(self.write_path, os.O_WRONLY)
            print(f"Write pipe opened successfully: {self.write_path} (fd: {self.write_fd})")
        except Exception as e:
            print(f"🚨 Error opening write pipe {self.write_path}: {e}")
            self.close_pipes()
            return False
        print("Both pipes set up successfully.")
        return True

    def close_pipes(self):
        closed_count = 0
        if self.write_fd is not None:
            try:
                os.close(self.write_fd)
                closed_count += 1
            except OSError as e:
                print(f"Error closing write pipe fd {self.write_fd}: {e}")
            finally:
                self.write_fd = None
        if self.read_fd is not None:
            try:
                os.close(self.read_fd)
                closed_count += 1
            except OSError as e:
                print(f"Error closing read pipe fd {self.read_fd}: {e}")
            finally:
                self.read_fd = None
        if closed_count > 0:
            print(f"{closed_count} pipe(s) closed.")

    def send_event(self, event_data):
        if self.write_fd is None:
            print("Error: Write pipe is not open for sending.")
            return False

        if not event_data.endswith('\n'):
            event_data += '\n'
        message = event_data.encode('utf-8')

        try:
            bytes_written = os.write(self.write_fd, message)
            if bytes_written < len(message):
                print(f"Warning: Partial write to pipe. Sent {bytes_written}/{len(message)} bytes for '{event_data.strip()}'")
            return True
        except OSError as e:
            if e.errno == errno.EAGAIN or e.errno == errno.EWOULDBLOCK:
                print(f"Warning: Write pipe buffer full when trying to send '{event_data.strip()}'. Event might be missed.")
            else:
                print(f"Error writing to pipe: {e} (errno={e.errno})")
            return False
        except Exception as e:
            print(f"Unexpected error sending event: {e}")
            return False

    def receive_event(self):
        if self.read_fd is None:
            return None
        try:
            chunk = os.read(self.read_fd, 4096)
            self.read_buffer += chunk

            if b'\n' in self.read_buffer:
                message, self.read_buffer = self.read_buffer.split(b'\n', 1)
                decoded_message = message.decode('utf-8').strip()
                # print(f"Received: '{decoded_message}'")
                return decoded_message
            else:
                return None

        except OSError as e:
            if e.errno == errno.EAGAIN or e.errno == errno.EWOULDBLOCK:
                return None
            else:
                print(f"Error reading from pipe: {e} (errno={e.errno})")
                return None
        except Exception as e:
            print(f"Unexpected error receiving event: {e}")
            return None