"""Output frames from encoder"""


class Output:
    """Handles output functionality of encoders"""

    def __init__(self):
        """Start output, with recording set to False"""
        self.recording = False

    def start(self):
        """Start recording"""
        self.recording = True

    def stop(self):
        """Stop recording"""
        self.recording = False

    def outputframe(self, frame, keyframe=True):
        """Outputs frame from encoder

        :param frame: Frame
        :type frame: bytes
        :param keyframe: Whether frame is a keyframe, defaults to True
        :type keyframe: bool, optional
        """
        pass
