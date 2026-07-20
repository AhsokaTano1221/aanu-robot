import time
try:
    from picamera2 import Picamera2, Preview
    from picamera2.encoders import H264Encoder, JpegEncoder
    from picamera2.outputs import FileOutput
    from libcamera import Transform
    HAS_PICAMERA = True
except ImportError:
    HAS_PICAMERA = False
from threading import Condition
import io
import os

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        """Initialize the StreamingOutput class."""
        self.frame = None
        self.condition = Condition()  # Initialize the condition variable for thread synchronization

    def write(self, buf: bytes) -> int:
        """Write a buffer to the frame and notify all waiting threads."""
        with self.condition:
            self.frame = buf             # Update the frame buffer with new data
            self.condition.notify_all()  # Notify all waiting threads that new data is available
        return len(buf)

class Camera:
    def __init__(self, preview_size: tuple = (640, 480), hflip: bool = False, vflip: bool = False, stream_size: tuple = (400, 300)):
        """Initialize the Camera class."""
        if HAS_PICAMERA:
            self.camera = Picamera2()  # Initialize the Picamera2 object
            self.transform = Transform(hflip=1 if hflip else 0, vflip=1 if vflip else 0)  # Set the transformation for flipping the image
            preview_config = self.camera.create_preview_configuration(main={"size": preview_size}, transform=self.transform)  # Create the preview configuration
            self.camera.configure(preview_config)  # Configure the camera with the preview settings
            
            # Configure video stream
            self.stream_size = stream_size  # Set the size of the video stream
            self.stream_config = self.camera.create_video_configuration(main={"size": stream_size}, transform=self.transform)  # Create the video configuration
            self.streaming_output = StreamingOutput()  # Initialize the streaming output object
            self.streaming = False  # Initialize the streaming flag
        else:
            self.camera = None
            self.streaming = False

    def start_image(self) -> None:
        """Start the camera preview and capture."""
        if HAS_PICAMERA:
            self.camera.start_preview(Preview.QTGL)  # Start the camera preview using the QTGL backend
            self.camera.start()                      # Start the camera
        else:
            print("[Mock Camera] Starting preview...")

    def save_image(self, filename: str) -> dict:
        """Capture and save an image to the specified file."""
        if HAS_PICAMERA:
            try:
                started_locally = False
                if not self.camera.started:
                    self.camera.start()
                    started_locally = True
                metadata = self.camera.capture_file(filename)  # Capture an image and save it to the specified file
                if started_locally:
                    self.camera.stop()
                return metadata                              # Return the metadata of the captured image
            except Exception as e:
                print(f"Error capturing image: {e}")         # Print error message if capturing fails
                return None                                  # Return None if capturing fails
        else:
            print(f"[Mock Camera] Simulating capture: Saved mock image to {filename}")
            with open(filename, 'wb') as f:
                f.write(b'MOCK_IMAGE_DATA')
            return {"mock": True}

    def start_stream(self, filename: str = None) -> None:
        """Start the video stream or recording."""
        if HAS_PICAMERA:
            if not self.streaming:
                if self.camera.started:
                    self.camera.stop()                         # Stop the camera if it is currently running
                
                self.camera.configure(self.stream_config)      # Configure the camera with the video stream settings
                if filename:
                    encoder = H264Encoder()                    # Use H264 encoder for video recording
                    output = FileOutput(filename)              # Set the output file for the recorded video
                else:
                    encoder = JpegEncoder()                    # Use Jpeg encoder for streaming
                    output = FileOutput(self.streaming_output) # Set the streaming output object
                self.camera.start_recording(encoder, output)   # Start recording or streaming
                self.streaming = True                          # Set the streaming flag to True
        else:
            print("[Mock Camera] Starting stream...")

    def stop_stream(self) -> None:
        """Stop the video stream or recording."""
        if HAS_PICAMERA:
            if self.streaming:
                try:
                    self.camera.stop_recording()               # Stop the recording or streaming
                    self.streaming = False                     # Set the streaming flag to False
                except Exception as e:
                    print(f"Error stopping stream: {e}")       # Print error message if stopping fails
        else:
            print("[Mock Camera] Stopping stream...")

    def get_frame(self) -> bytes:
        """Get the current frame from the streaming output."""
        if HAS_PICAMERA:
            with self.streaming_output.condition:
                self.streaming_output.condition.wait()         # Wait for a new frame to be available
                return self.streaming_output.frame             # Return the current frame
        else:
            return b'MOCK_FRAME_DATA'

    def save_video(self, filename: str, duration: int = 10) -> None:
        """Save a video for the specified duration."""
        self.start_stream(filename)                        # Start the video recording
        time.sleep(duration)                               # Record for the specified duration
        self.stop_stream()                                 # Stop the video recording

    def close(self) -> None:
        """Close the camera."""
        if HAS_PICAMERA:
            if self.streaming:
                self.stop_stream()                             # Stop the streaming if it is active
            self.camera.close()                                # Close the camera
        else:
            print("[Mock Camera] Closing camera...")

if __name__ == '__main__':
    print('Program is starting ... ')                    # Print a message indicating the start of the program
    camera = Camera()                                    # Create a Camera instance

    # Check if display is available (to avoid XCB connection crash over SSH)
    if not os.environ.get('DISPLAY'):
        print("⚠️ Warning: No DISPLAY environment variable detected. Running headlessly.")
        print("We will skip GUI preview to avoid Qt connection errors and directly capture/save an image instead.")
        print("Capture image...")
        camera.save_image(filename="image.jpg")              # Capture and save an image
        print("📸 Successfully saved image.jpg without GUI display.")
        camera.close()
    else:
        print("View image...")
        camera.start_image()                                 # Start the camera preview
        time.sleep(10)                                       # Wait for 10 seconds
        
        print("Capture image...")
        camera.save_image(filename="image.jpg")              # Capture and save an image
        time.sleep(1)                                        # Wait for 1 second
        camera.close()