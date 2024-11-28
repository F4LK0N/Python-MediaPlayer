import tkinter as tk
from tkinter import filedialog, messagebox
import wave
import os
import pyaudio
import threading
import time


class App:
    """Main application class to handle the user interface and interactions."""

    def __init__(self):
        # Initialize the main application window
        self.window = tk.Tk()
        self.window.title("Audio Waveform")
        self.window.geometry("1200x600")
        self.window.minsize(600, 300)
        self.window.protocol("WM_DELETE_WINDOW", self.close) # Handle window close event

        self.waveform = None
        self.init_gui_waveform()

        self.init_gui_file()

        self.player = None
        self.init_gui_player()

    def close(self):
        """Handle application close event, including cleanup."""
        if tk.messagebox.askyesno("Exit", "Exit program?"):
            if self.player is not None:
                self.player.close()
            self.window.destroy()

    def init_gui_waveform(self):
        """Initialize the GUI section for displaying the waveform."""
        self.gui_waveform_frame = tk.Frame(self.window)
        self.gui_waveform_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.gui_waveform_canvas = WaveformCanvas(self, self.gui_waveform_frame)

    def init_gui_file(self):
        """Initialize the GUI section for file loading."""
        self.gui_file_frame = tk.Frame(self.window)
        self.gui_file_frame.pack()

        self.gui_file_load = tk.Button(self.gui_file_frame, text="LOAD", command=self.action_load)
        self.gui_file_load.pack(pady=10)

    def init_gui_player(self):
        """Initialize the GUI section for audio player controls."""
        self.gui_player_frame = tk.Frame(self.window)
        self.gui_player_frame.pack()

        # Play/Pause button (disabled initially)
        self.gui_player_play_pause = tk.Button(self.gui_player_frame, text="PLAY", command=self.action_play_pause, state=tk.DISABLED)
        self.gui_player_play_pause.pack(side=tk.LEFT)

        # Stop button (disabled initially)
        self.gui_player_stop = tk.Button(self.gui_player_frame, text="STOP", command=self.action_stop, state=tk.DISABLED)
        self.gui_player_stop.pack(side=tk.LEFT)

        # Repeat option
        self.gui_player_repeat_var = tk.BooleanVar()
        self.gui_player_repeat = tk.Checkbutton(self.gui_player_frame, text="REPEAT", variable=self.gui_player_repeat_var, command=self.action_repeat)
        self.gui_player_repeat.pack(side=tk.LEFT)

    def update_gui_player_play_pause(self, playing):
        """Update the play/pause button text based on playback state."""
        if self.gui_player_play_pause is None:
            return

        # Update button text depending on whether audio is playing
        if playing:
            self.gui_player_play_pause.config(text="PAUSE")
        else:
            self.gui_player_play_pause.config(text="PLAY")

    def run(self):
        """Start the Tkinter event loop."""
        self.window.mainloop()

    def action_load(self):
        """Handles file selection and initiates waveform drawing."""
        path = filedialog.askopenfilename(
            title="Select a WAV File", filetypes=[("WAV files", "*.wav")]
        )
        if not path:
            return

        # Load and process the selected WAV file
        try:
            if self.waveform is not None:
                self.waveform.close() # Close any previously loaded waveform
            self.waveform = Waveform()
            self.waveform.open(path) # Open and process the selected file
        except Exception as e:
            messagebox.showerror("Error", f"Waveform: {e}")

        # Update the waveform display
        self.gui_waveform_canvas.draw_title(os.path.basename(path))
        self.gui_waveform_canvas.draw_waveform(self.waveform.data)
        self.gui_waveform_canvas.draw_position(0)

        # Initialize the audio player for the selected file
        try:
            if self.player is not None:
                self.player.stop()
                self.player.close() # Ensure any previous audio playback is stopped
            self.player = AudioPlayer(self)
            self.player.open(path)
            self.player.start() # Start the audio player thread
        except Exception as e:
            messagebox.showerror("Error", f"AudioPlayer: {e}")

        # Enable play and stop buttons
        self.gui_player_play_pause.config(state=tk.NORMAL, text="PLAY")
        self.gui_player_stop.config(state=tk.NORMAL)

    def action_play_pause(self):
        """Toggle between play and pause states."""
        if self.player is None:
            return

        # Play or pause audio based on the current state
        if self.player.playing is False:
            self.player.play()
            self.update_gui_player_play_pause(True)
        else:
            self.player.pause()
            self.update_gui_player_play_pause(False)

    def action_stop(self):
        """Stops the playing audio."""
        if self.player is None:
            return

        self.player.stop()
        self.update_gui_player_play_pause(False)

    def action_repeat(self):
        """Sets the repeat option."""
        if self.player is None:
            return

        self.player.repeat = self.gui_player_repeat_var.get()


class Waveform:
    """Handles processing, validation, and storage of waveform data."""

    def __init__(self):
        self.path = None
        self.data = None
        self.channels = 0
        self.width = 0
        self.rate = 0
        self.frames = 0

    def close(self):
        """Resets waveform data and file properties."""
        self.path = None
        self.data = None
        self.channels = 0
        self.width = 0
        self.rate = 0
        self.frames = 0

    def open(self, path):
        """Opens and processes the WAV file to extract stereo waveform data."""
        self.close()
        self.path = path

        try:
            with wave.open(self.path, 'r') as wav_file:
                self.channels = wav_file.getnchannels()
                self.width = wav_file.getsampwidth()
                self.rate = wav_file.getframerate()
                self.frames = wav_file.getnframes()

                # Validate WAV parameters
                if self.channels not in [1, 2]:
                    raise ValueError("Unsupported number of channels.")
                if self.width not in [1, 2]:
                    raise ValueError("Unsupported sample width.")

                # Read and process waveform data
                frames = wav_file.readframes(self.frames)
                raw_data = self.frames_normalize(frames)

                # Mono
                if self.channels == 1:
                    # Convert by duplicating channels
                    self.data = self.channels_normalize_from_mono(raw_data)
                # Stereo
                else:
                    # Pair left and right channels
                    self.data = self.channels_normalize_from_stereo(raw_data)

        except Exception as e:
            raise Exception(f"Error opening file: {e}")

    def frames_normalize(self, frames):
        """Converts raw frame data to integer values."""
        if self.width == 1:
            # 8-bit samples: unsigned, range 0-255, center by subtracting 128
            return [x - 128 for x in frames]
        elif self.width == 2:
            # 16-bit samples: signed, range -32768 to 32767
            return [int.from_bytes(frames[i:i + 2], 'little', signed=True) for i in range(0, len(frames), 2)]

    def channels_normalize_from_stereo(self, data):
        """Pairs stereo channels into tuples (L, R)."""
        return [(data[i], data[i + 1]) for i in range(0, len(data), 2)]

    def channels_normalize_from_mono(self, data):
        """Converts mono data to stereo by duplicating each sample."""
        return [(sample, sample) for sample in data]


class WaveformCanvas:
    """Handles rendering of the waveform on a canvas."""

    def __init__(self, app, window):
        self.app = app

        self.canvas = tk.Canvas(window, bg="white", width=1200, height=400)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.canvas.bind("<Button-1>", self.action_click)
        self.canvas.bind("<Configure>", self.event_resize)

    def draw_title(self, title):
        """Draws the title of the canvas."""
        self.canvas.delete("title")
        self.canvas.create_text(
            self.canvas.winfo_width() // 2,
            10,
            text=f"{title}",
            fill="black",
            tags="title"
        )

    def draw_waveform(self, data):
        """Draws the waveform on the canvas."""
        self.canvas.delete("channel_left")
        self.canvas.delete("channel_right")

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        mid_y = height // 2

        # Calculate scaling factors
        x_scale = max(1, len(data) // width)  # Downsample if necessary
        y_scale = max(
            1,
            max(max(abs(left), abs(right)) for left, right in data) // (height // 2)
        )  # Normalize amplitude

        for x in range(0, width):
            index = x * x_scale
            if index < len(data):
                left_amplitude = data[index][0] // y_scale
                right_amplitude = data[index][1] // y_scale

                # Draw left channel
                self.canvas.create_line(
                    x, mid_y, x, mid_y - left_amplitude, fill="blue", tags="channel_left"
                )

                # Draw right channel
                self.canvas.create_line(
                    x, mid_y, x, mid_y + right_amplitude, fill="green", tags="channel_right"
                )

    def draw_position(self, position):
        """Updates the position indicator on the waveform."""
        self.canvas.delete("position")

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        if self.app.waveform:
            x_scale = max(1, len(self.app.waveform.data) // width)  # Downsample if necessary
            position_x = (position+1) // x_scale
            self.canvas.create_line(
                position_x, 0, position_x, height, fill="red", tags="position"
            )

    def action_click(self, event):
        """Sets the audio player position based on a click event."""
        if self.app.waveform is None or self.app.player is None:
            return

        # Get the waveform data length and canvas width
        data_length = len(self.app.waveform.data)
        canvas_width = self.canvas.winfo_width()

        # Calculate the new position in the audio data
        click_x = event.x
        position = int((click_x / canvas_width) * data_length)

        # Set the player's position
        self.app.player.file_position(position)

        # Update the position indicator on the canvas
        self.draw_position(position)

    def event_resize(self, event):
        """Handles resizing of the canvas."""
        print("RESIZE")
        if self.app.waveform is not None and self.app.waveform.data is not None:
            self.draw_waveform(self.app.waveform.data)  # Redraw waveform

class AudioPlayer(threading.Thread):
    """Handles playing of WAV files using PyAudio."""

    def __init__(self, app):
        super().__init__()
        self.app = app

        self.file = None
        self.pyaudio = None
        self.stream = None

        self.playing = False  # Indicates if the audio is currently playing
        self.repeat = False  # Indicates if the audio is currently playing on repeat mode
        self.position = 0  # Start position of audio playback

    def file_open(self, path):
        """Opens the WAV file."""
        try:
            self.file = wave.open(path, 'r')
        except Exception as e:
            raise Exception(f"Error loading file: {e}")

    def file_read(self, num_frames):
        """Reads a specified number of frames from the file."""
        if self.file is None:
            return None

        try:
            return self.file.readframes(num_frames)
        except Exception as e:
            raise Exception(f"Error reading file: {e}")

    def file_position(self, position=None):
        """Gets or sets the current file position."""
        if self.file is None:
            return 0

        if position is not None:
            try:
                max_position = self.file.getnframes()
                position = max(0, min(position, max_position))
                self.file.setpos(position)
            except Exception as e:
                raise Exception(f"Error writing file position: {e}")

        try:
            return self.file.tell()
        except Exception as e:
            raise Exception(f"Error reading file position: {e}")

    def file_close(self):
        """Closes the WAV file."""
        if self.file is not None:
            try:
                self.file.close()
                self.file = None
            except Exception as e:
                raise Exception(f"Error closing file: {e}")

    def stream_open(self):
        """Opens the PyAudio stream."""
        if self.file is None:
            return

        if self.pyaudio is None:
            try:
                self.pyaudio = pyaudio.PyAudio()
            except Exception as e:
                raise Exception(f"Error loading module: {e}")

        if self.stream is None:
            try:
                self.stream = self.pyaudio.open(
                    format=self.pyaudio.get_format_from_width(self.file.getsampwidth()),
                    channels=self.file.getnchannels(),
                    rate=self.file.getframerate(),
                    output=True)
            except Exception as e:
                raise Exception(f"Error loading stream: {e}")

    def stream_write(self, data):
        """Writes data to the audio stream."""
        if self.stream is None:
            return

        try:
            self.stream.write(data)
        except Exception as e:
            raise Exception(f"Error writing to stream: {e}")

    def stream_close(self):
        """Stops and closes the PyAudio stream."""
        if self.stream is not None:
            try:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
            except Exception as e:
                raise Exception(f"Error closing stream: {e}")

        if self.pyaudio is not None:
            try:
                self.pyaudio.terminate()
                self.pyaudio = None
            except Exception as e:
                raise Exception(f"Error closing module: {e}")

    def open(self, path):
        self.close()
        self.file_open(path)
        self.file_position(0)
        self.stream_open()

    def close(self):
        self.stop()
        self.stream_close()
        self.file_close()

    def play(self):
        """Resumes or starts audio playback."""
        if self.stream is None:
            self.playing = False
            return
        self.playing = True

    def pause(self):
        """Pauses audio playback."""
        self.playing = False

    def stop(self):
        """Stops audio playback and resets the position."""
        self.playing = False
        self.file_position(0)
        self.app.gui_waveform_canvas.draw_position(self.file_position())

    def run(self):
        """Plays the WAV file using PyAudio."""
        try:
            while self.stream is not None:
                if self.playing:
                    data = self.file_read(1024)
                    if (data is None) or (self.file.getnframes() == self.file_position()):
                        self.file_position(0)
                        self.playing = self.repeat
                        self.app.update_gui_player_play_pause(self.playing)
                    else:
                        self.stream_write(data)
                        self.file_position(self.file_position() + 1024)
                    self.app.gui_waveform_canvas.draw_position(self.file_position())
                else:
                    time.sleep(0.1)
        except Exception as e:
            self.stop()
            print(f"AudioPlayer: Error playing file: {e}")

if __name__ == "__main__":
    app = App()
    app.run()
