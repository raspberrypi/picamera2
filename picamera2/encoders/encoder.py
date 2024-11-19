"""Encoder functionality"""

import threading
from enum import Enum

import av
from libcamera import controls

import picamera2.formats as formats

from ..outputs import Output
from ..request import _MappedBuffer


class Quality(Enum):
    """Enum type to describe the quality wanted from an encoder.

    This may be passed if a specific value (such as bitrate) has not been set.
    """

    VERY_LOW = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    VERY_HIGH = 4


class Encoder:
    """
    Base class for encoders.

    Mostly this defines the API for derived encoder classes, but it also handles optional audio encoding.
    For audio, a separate thread is started, which encodes audio packets and forwards them to the
    encoder's output object(s). This only work when the output object understands the audio stream,
    meaning that (at the time of writing) this must be a PyavOutput (though you could send output there
    via a CircularOutput2).

    Additional audio parameters:
    audio - set to True to enable audio encoding and output.
    audio_input - list of parameters that is passed to PyAv.open to create the audio input.
    audio_output - list of parameters passed to PyAv add_stream to define the audio codec and output stream.
    audio_sync - value (in us) by which to advance the audio stream to better sync with the video.

    Reasonable defaults are supplied so that applications can often just set the audio property to True.
    The audio_input and audio_output parameters are passed directly to PyAV, so will accept whatever PyAV
    understands.
    """

    def __init__(self):
        """Initialises encoder"""
        self._width = 0
        self._height = 0
        self._stride = 0
        self._format = None
        self._output = []
        self._running = False
        self._name = None
        self._lock = threading.Lock()
        self.firsttimestamp = None
        self.frame_skip_count = 1
        self._skip_count = 0
        self._output_lock = threading.Lock()
        # Set to True to enable audio.
        self.audio = False
        # These parameters are passed to Pyav to open the input audio container.
        self.audio_input = {'file': 'default', 'format': 'pulse'}
        # THese parameters are passed to Pyav for creating the encoded audio output stream.
        self.audio_output = {'codec_name': 'aac'}
        self.audio_sync = -100000  # in us, so by default, delay audio by 100ms
        self._audio_start = threading.Event()

    @property
    def running(self):
        return self._running

    @property
    def width(self):
        """Gets width

        :return: Width of frames
        :rtype: int
        """
        return self._width

    @width.setter
    def width(self, value):
        """Sets width

        :param value: Width
        :type value: int
        :raises RuntimeError: Failed to set width
        """
        if not isinstance(value, int):
            raise RuntimeError("Width must be integer")
        self._width = value

    @property
    def height(self):
        """Gets height

        :return: Height of frames
        :rtype: int
        """
        return self._height

    @height.setter
    def height(self, value):
        """Sets height

        :param value: Height
        :type value: int
        :raises RuntimeError: Failed to set height
        """
        if not isinstance(value, int):
            raise RuntimeError("Height must be integer")
        self._height = value

    @property
    def size(self):
        """Gets size

        :return: Size of frames as (width, height)
        :rtype: tuple
        """
        return (self._width, self._height)

    @size.setter
    def size(self, value):
        """Sets size

        :param value: Size
        :type value: tuple
        :raises RuntimeError: Failed to set size
        """
        if not isinstance(value, tuple) or len(value) != 2:
            raise RuntimeError("Size must be a tuple of two integers")
        self.width, self.height = value

    @property
    def stride(self):
        """Gets stride

        :return: Stride
        :rtype: int
        """
        return self._stride

    @stride.setter
    def stride(self, value):
        """Sets stride

        :param value: Stride
        :type value: int
        :raises RuntimeError: Failed to set stride
        """
        if not isinstance(value, int):
            raise RuntimeError("Stride must be integer")
        self._stride = value

    @property
    def format(self):
        """Get current format

        :return: Current format
        :rtype: int
        """
        return self._format

    @format.setter
    def format(self, value):
        """Sets input format to encoder

        :param value: Format
        :type value: str
        :raises RuntimeError: Invalid format
        """
        formats.assert_format_valid(value)
        self._format = value

    @property
    def output(self):
        """Gets output objects

        :return: Output object list or single Output object
        :rtype: List[Output]
        """
        if len(self._output) == 1:
            return self._output[0]
        else:
            return self._output

    @output.setter
    def output(self, value):
        """Sets output object, to write frames to

        :param value: Output object
        :type value: Output
        :raises RuntimeError: Invalid output passed
        """
        if isinstance(value, list):
            for out in value:
                if not isinstance(out, Output):
                    raise RuntimeError("Must pass Output")
        elif isinstance(value, Output):
            value = [value]
        else:
            raise RuntimeError("Must pass Output")
        self._output = value

    @property
    def name(self):
        """Gets stream name

        :return: Name
        :rtype: str
        """
        return self._name

    @name.setter
    def name(self, value):
        """Sets stream name

        :param value: Name
        :type value: str
        :raises RuntimeError: Failed to set name
        """
        if not isinstance(value, str):
            raise RuntimeError("Name must be string")
        self._name = value

    def encode(self, stream, request):
        """Encode a frame

        :param stream: Stream
        :type stream: stream
        :param request: Request
        :type request: request
        """
        if self.audio:
            self._audio_start.set()  # Signal the audio encode thread to start.
        if self._skip_count == 0:
            with self._lock:
                self._encode(stream, request)
        self._skip_count = (self._skip_count + 1) % self.frame_skip_count

    def _encode(self, stream, request):
        if isinstance(stream, str):
            stream = request.stream_map[stream]
        timestamp_us = self._timestamp(request)
        with _MappedBuffer(request, stream) as b:
            self.outputframe(b, keyframe=True, timestamp=timestamp_us)

    def start(self, quality=None):
        with self._lock:
            if self._running:
                raise RuntimeError("Encoder already running")
            self._setup(quality)
            self._running = True
            self.firsttimestamp = None
            for out in self._output:
                out.start()
            self._start()

            # Start the audio, if that's been requested.
            if self.audio:
                self._audio_input_container = av.open(**self.audio_input)
                self._audio_input_stream = self._audio_input_container.streams.get(audio=0)[0]
                self._audio_output_container = av.open("/dev/null", 'w', format="null")
                self._audio_output_stream = self._audio_output_container.add_stream(**self.audio_output)
                # Outputs that can handle audio need to be told about its existence.
                for out in self._output:
                    out._add_stream(self._audio_output_stream, **self.audio_output)
                self._audio_thread = threading.Thread(target=self._audio_thread_func, daemon=True)
                self._audio_start.clear()
                self._audio_thread.start()  # audio thread will wait for the _audio_start event.

    def _start(self):
        pass

    def stop(self):
        with self._lock:
            if not self._running:
                raise RuntimeError("Encoder already stopped")
            self._running = False
            self._stop()
            if self.audio:
                self._audio_start.set()  # just in case it wasn't!
                self._audio_thread.join()
                self._audio_input_container.close()
                self._audio_output_container.close()
            for out in self._output:
                out.stop()

    def _stop(self):
        pass

    def outputframe(self, frame, keyframe=True, timestamp=None, packet=None, audio=False):
        """Writes a frame

        :param frame: Frame
        :type frame: bytes
        :param keyframe: Whether frame is a keyframe or not, defaults to True
        :type keyframe: bool, optional
        """
        with self._output_lock:
            for out in self._output:
                out.outputframe(frame, keyframe, timestamp, packet, audio)

    def _setup(self, quality):
        pass

    def _timestamp(self, request):
        # The sensor timestamp is the most accurate one, so we'll fetch that.
        ts = int(request.request.metadata[controls.SensorTimestamp] / 1000)  # ns to us
        if self.firsttimestamp is None:
            self.firsttimestamp = ts
            timestamp_us = 0
        else:
            timestamp_us = ts - self.firsttimestamp
        return timestamp_us

    def _handle_audio_packet(self, audio_packet):
        # Write out audio an packet, dealing with timestamp adjustments.
        time_scale_factor = 1000000 * self._audio_output_stream.codec_context.time_base
        delta = int(self.audio_sync / time_scale_factor)  # convert to audio time base
        audio_packet.pts -= delta
        audio_packet.dts -= delta
        timestamp = int(audio_packet.pts * time_scale_factor)  # want this in us
        if audio_packet.pts >= 0:
            self.outputframe(None, True, timestamp, audio_packet, True)

    def _audio_thread_func(self):
        # Audio thread that fetches audio packets, encodes them and forwards them to the output.
        # The output has to be able to understand audio, which means using a PyavOutput.
        # _audio_start gets signalled when the first video frame is submitted for encode, which will hopefully
        # keep the audio_sync adjustment more similar across different devices. Until that happens, though,
        # we must keep consuming and discarding the audio.
        for _ in self._audio_input_container.decode(self._audio_input_stream):
            if self._audio_start.isSet():
                break

        for audio_frame in self._audio_input_container.decode(self._audio_input_stream):
            if not self._running:
                break
            for audio_packet in self._audio_output_stream.encode(audio_frame):
                self._handle_audio_packet(audio_packet)

        # Flush out any remaining audio packets.
        for audio_packet in self._audio_output_stream.encode(None):
            self._handle_audio_packet(audio_packet)
