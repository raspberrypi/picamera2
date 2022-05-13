import collections


class Output:
    def __init__(self):
        self.recording = False

    def start(self):
        self.recording = True

    def stop(self):
        self.recording = False

    def outputframe(self, frame, keyframe=True):
        pass
