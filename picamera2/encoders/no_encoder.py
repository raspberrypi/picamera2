"""
Using picamera2.Encoder with camera.start_recording will return `RuntimeError: Must pass Output` if not using a Output class as output.
This class allows to bypass the need for the picamera2.Encoder class. Then you can create an output class with io.BufferedIOBase.

Example:
class VideoOutput(io.BufferedIOBase):
    def __init__(self):
        super().__init__()
        self.img = np.zeros((480, 640, 3), dtype=np.uint8)
        self.condition = Condition()
        self.timeout = 1
        self.processed = False

    def write(self, img):
        # Reshape from 2-d array
        np_image = img.reshape((480, 640, 3))
        with self.condition:
            self.img = np_image
            self.processed = False
            self.condition.notify_all()

    def wait_main(self):
        # Do not wait for next notify if not processed
        with self.condition:
            if self.processed:
                self.condition.wait(self.timeout)
            self.processed = True

    def wait(self):
        with self.condition:
            return self.condition.wait(self.timeout)

This dummy encoder provides the required interface (encode, start, _setup, stop)
for use with camera.start_recording(encoder, output). It simply writes the raw frame
data to the provided output without performing any encoding.
"""

from typing import Any, Optional, IO

class NoEncoder:
    """
    A dummy encoder that bypasses actual encoding.

    This class is provided for compatibility with systems that expect an encoder object.
    It implements the methods _setup, encode, start, and stop, but only encode performs any action.
    """

    def __init__(self, name: str = "main", output: Optional[IO] = None):
        """
        Initialize the NoEncoder instance.

        Args:
            name (str): Identifier used to select the frame buffer.
            output (IO, optional): The destination where the frame data will be written.
                                   Must have a write() method.
        """
        self.name = name
        self.output = output
        self.width: Optional[int] = None
        self.height: Optional[int] = None
        self.format: Optional[str] = None  # e.g., "XRGB8888"
        self.stride: Optional[int] = None
        self.framerate: Optional[int] = None

    def _setup(self, quality: Any = None) -> None:
        """
        Prepare the encoder before recording starts.

        This method exists to comply with the required interface, though no setup is needed
        for this bypass encoder.

        Args:
            quality: Optional parameter for quality settings (unused).
        """
        pass

    def encode(self, stream: Any, request: Any) -> None:
        """
        Process and write a single frame to the output.

        This method is called repeatedly during recording. It retrieves the frame buffer from
        the 'request' object and writes it directly to the output. If the frame's format is
        'XRGB8888', the alpha channel is removed before writing.

        Args:
            stream: Unused parameter included for API compatibility.
            request: An object that must provide:
                     - config: A dictionary with configuration data (expects "main" with "format").
                     - make_buffer(name): A method to retrieve the frame buffer for the given name.
        """
        # If the format hasn't been set yet, retrieve it from the request configuration.
        if self.format is None:
            self.format = request.config.get("main", {}).get("format")
        
        # Retrieve the frame buffer using the provided name.
        frame = request.make_buffer(self.name)
        
        # Check if the frame format indicates that an alpha channel is present.
        if self.format == "XRGB8888":
            # Reshape the frame buffer into a 2D array where each pixel is 4 components (e.g., X, R, G, B),
            # then discard the first column (alpha channel) and write only the RGB components.
            processed_frame = frame.reshape(-1, 4)[:, 1:]
            self.output.write(processed_frame)
        else:
            # Write the frame as-is for formats that do not include an alpha channel.
            self.output.write(frame)

    def start(self, quality: Any = None) -> None:
        """
        Start the encoder.

        This method exists to comply with the required interface but does not perform any actions
        because no encoding is needed.

        Args:
            quality: Optional parameter for quality settings (unused).
        """
        pass

    def stop(self) -> None:
        """
        Stop the encoder.

        This method exists to comply with the required interface. No actions are taken when stopping.
        """
        pass
