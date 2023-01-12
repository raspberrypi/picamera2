from concurrent.futures import Future
from typing import Callable, Optional


class Job:
    """
    A Job is an operation that can be delegated to the camera event loop to perform

    Such as capturing and returning an image. Most jobs only do a single
    thing, like copying out a numpy array, and so consist of a single function
    that we pass to do this.

    But some jobs may take several frames to complete, for example if they involve
    mode switches, or waiting for certain controls to take effect. Here we need
    to submit a list of functions to perform, and as each function, representing
    a stage of the job, completes, then we will move on to the next function in
    the list when the next frame arrives.

    Jobs are normally created by the Picamera2.dispatch_functions method, though
    most common operations have dedicated methods to do this, such as
    Picamera2.switch_mode_and_capture_array.
    """

    def __init__(self, functions: list[Callable], signal_function: Optional[Callable] = None) -> None:
        self._functions = functions
        self._future = Future()
        self._future.set_running_or_notify_cancel()
        self._signal_function = signal_function
        self._result = None

        # I wonder if there is any useful information we could collect, number
        # of frames it took for things to finish, maybe intermediate results...
        self.calls = 0

    def execute(self) -> bool:
        """Try to execute this Job.

        It will return True if it finishes, or False if it needs to be tried again.
        """
        assert self._functions, "Job already completed!"

        try:
            # Each function making up the Job returns two things: whether it's
            # "done", in which case we pop it off the list so that the function
            # in the list will run with the next frame (otherwise we leave it there
            # to try again next time). Secondly, it returns a value that counts
            # as its "result" once it completes.
            done, result = self._functions[0]()
            self.calls += 1
            if done:
                self._functions.pop(0)

                # When no functions are left, the entire job is complete.
                if not self._functions:
                    self._result = result

        except Exception as e:
            self._future.set_exception(e)
            self._functions = []

        return not self._functions

    def signal(self) -> None:
        """Signal that the job is finished."""
        assert not self._functions, "Job not finished!"

        if not self._future.done():
            self._future.set_result(self._result)
        if self._signal_function:
            self._signal_function(self)

    def get_result(self):
        """This fetches the 'final result' of the job

        (being given by the return value of the last function executed). It will block
        if necessary for the job to complete.
        """
        return self._future.result()
