from collections import deque
from concurrent.futures import Future
from logging import getLogger
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from scicamera.frame import CameraFrame
from scicamera.request import CompletedRequest, LoopTask
from scicamera.typing import TypedFuture

_log = getLogger(__name__)


class RequestMachinery:
    """RequestMachinery is a helper class for the Camera class."""

    def __init__(self) -> None:
        self._requests = deque()
        self._request_callbacks = []
        self._task_deque: Deque[LoopTask] = deque()

    def add_request_callback(self, callback: Callable[[CompletedRequest], None]):
        """Add a callback to be called when every request completes.

        Note that the request is only valid within the callback, and will be
        deallocated after the callback returns.

        :param callback: The callback to be called
        :type callback: Callable[[CompletedRequest], None]
        """
        self._request_callbacks.append(callback)

    def remove_request_callback(self, callback: Callable[[CompletedRequest], None]):
        """Remove a callback previously added with add_request_callback.

        :param callback: The callback to be removed
        :type callback: Callable[[CompletedRequest], None]
        """
        self._request_callbacks.remove(callback)

    def add_completed_request(self, request: CompletedRequest) -> None:
        self._requests.append(request)

    def has_requests(self) -> bool:
        return len(self._requests) > 0

    def process_requests(self) -> None:
        # Safe copy and pop off all requests
        requests = list(self._requests)
        for _ in requests:
            self._requests.popleft()

        req_idx = 0
        while len(self._task_deque) and (req_idx < len(requests)):
            task = self._task_deque.popleft()
            _log.debug(f"Begin LoopTask Execution: {task.call}")
            try:
                if task.needs_request:
                    req = requests[req_idx]
                    req_idx += 1
                    task.future.set_result(task.call(req))
                else:
                    task.future.set_result(task.call())
            except Exception as e:
                _log.warning(f"Error in LoopTask {task.call}: {e}")
                task.future.set_exception(e)
            _log.debug(f"End LoopTask Execution: {task.call}")

        for request in requests:
            for callback in self._request_callbacks:
                try:
                    callback(request)
                except Exception as e:
                    _log.error(f"Error in request callback ({callback}): {e}")

        for req in requests:
            req.release()

    def _dispatch_loop_tasks(
        self, *args: LoopTask, config: Optional[dict] = None
    ) -> List[Future]:
        """The main thread should use this to dispatch a number of operations for the event
        loop to perform. The event loop will execute them in order, and return a list of
        futures which mature at the time the corresponding operation completes.
        """

        if config is None:
            tasks = args
        else:
            previous_config = self.camera_config
            # FIXME: the discarded request enough for test cases, but the correct
            # way to flag this is with the request.cookie, but that is currently
            # used to route between cameras. Fixable, but independent issue for now.
            tasks = (
                [
                    LoopTask.without_request(self._switch_mode, config),
                    LoopTask.with_request(self._discard_request),
                ]
                + list(args)
                + [
                    LoopTask.without_request(self._switch_mode, previous_config),
                ]
            )
        self._task_deque.extend(tasks)
        # Note that the below strips the config changes
        return [task.future for task in args]

    def _discard_request(self, request: CompletedRequest) -> None:
        pass

    def discard_frames(self, n_frames: int) -> TypedFuture[None]:
        """Discard the next ``n_frames`` in the queue."""
        return self._dispatch_loop_tasks(
            *[LoopTask.with_request(self._discard_request) for _ in range(n_frames)]
        )[-1]

    def _switch_mode(self, camera_config):
        self._stop()
        self._configure(camera_config)
        self._start()
        return self.camera_config

    def switch_mode(self, camera_config: dict) -> TypedFuture[dict]:
        """Switch the camera into another mode given by the camera_config."""
        return self._dispatch_loop_tasks(
            LoopTask.without_request(self._switch_mode, camera_config)
        )[0]

    def _capture_file(
        self, name, file_output, format, request: CompletedRequest
    ) -> dict:
        request.make_image(name).convert("RGB").save(file_output, format=format)
        return request.get_metadata()

    def capture_file(
        self, file_output, name: str = "main", format=None, config=None
    ) -> TypedFuture[dict]:
        return self._dispatch_loop_tasks(
            LoopTask.with_request(self._capture_file, name, file_output, format),
            config=config,
        )[0]

    def _capture_request(self, request: CompletedRequest):
        request.acquire()
        return request

    def capture_request(
        self, config: Optional[dict] = None
    ) -> TypedFuture[CompletedRequest]:
        """Fetch the next completed request from the camera system. You will be holding a
        reference to this request so you must release it again to return it to the camera system.
        """
        return self._dispatch_loop_tasks(
            LoopTask.with_request(self._capture_request), config=config
        )[0]

    def _capture_metadata(self, request: CompletedRequest):
        return request.get_metadata()

    def capture_metadata(self, config: Optional[dict] = None) -> Future:
        return self._dispatch_loop_tasks(
            LoopTask.with_request(self._capture_metadata), config=config
        )[0]

    # Buffer Capture Methods
    def _capture_buffer(self, name: str, request: CompletedRequest):
        return request.get_buffer(name)

    def capture_buffer(self, name="main", config: dict = None) -> Future[np.ndarray]:
        """Make a 1d numpy array from the next frame in the named stream."""
        return self._dispatch_loop_tasks(
            LoopTask.with_request(self._capture_buffer, name), config=config
        )[0]

    # Buffers and metadata
    def _capture_buffers_and_metadata(
        self, names: List[str], request: CompletedRequest
    ) -> Tuple[List[np.ndarray], dict]:
        return ([request.get_buffer(name) for name in names], request.get_metadata())

    def capture_buffers_and_metadata(
        self, names=["main"]
    ) -> TypedFuture[Tuple[List[np.ndarray], dict]]:
        """Make a 1d numpy array from the next frame for each of the named streams."""
        return self._dispatch_loop_tasks(
            LoopTask.with_request(self._capture_buffers_and_metadata, names)
        )[0]

    # Array Capture Methods
    def _capture_array(self, name, request: CompletedRequest):
        return request.make_array(name)

    def capture_array(
        self, name="main", config: Optional[dict] = None
    ) -> Future[np.ndarray]:
        """Make a 2d image from the next frame in the named stream."""
        return self._dispatch_loop_tasks(
            LoopTask.with_request(self._capture_array, name), config=config
        )[0]

    def _capture_arrays_and_metadata(
        self, names, request: CompletedRequest
    ) -> Tuple[List[np.ndarray], Dict[str, Any]]:
        return ([request.make_array(name) for name in names], request.get_metadata())

    def capture_arrays_and_metadata(
        self, names=["main"]
    ) -> TypedFuture[Tuple[List[np.ndarray], Dict[str, Any]]]:
        """Make 2d image arrays from the next frames in the named streams."""
        return self._dispatch_loop_tasks(
            LoopTask.with_request(self._capture_arrays_and_metadata, names)
        )[0]

    def _capture_image(self, name: str, request: CompletedRequest) -> Image.Image:
        return request.make_image(name)

    def capture_image(
        self, name: str = "main", config: Optional[dict] = None
    ) -> TypedFuture[Image.Image]:
        """Make a PIL image from the next frame in the named stream.

        :param name: Stream name, defaults to "main"
        :type name: str, optional
        :param wait: Wait for the event loop to finish an operation and signal us, defaults to True
        :type wait: bool, optional
        :param signal_function: Callback, defaults to None
        :type signal_function: function, optional
        :return: PIL Image
        :rtype: Image
        """
        return self._dispatch_loop_tasks(
            LoopTask.with_request(self._capture_image, name),
            config=config,
        )[0]

    def _capture_frame(self, name: str, request: CompletedRequest) -> CameraFrame:
        return CameraFrame.from_request(name, request)

    def capture_frame(
        self, name: str = "main", config=None
    ) -> TypedFuture[CameraFrame]:
        """Make a CameraFrame from the next frame in the named stream.

        :param name: Stream name, defaults to "main"
        :type name: str, optional
        """
        return self._dispatch_loop_tasks(
            LoopTask.with_request(self._capture_frame, name), config=config
        )[0]

    def capture_serial_frames(
        self, n_frames: int, name="main"
    ) -> List[TypedFuture[CameraFrame]]:
        """Capture a number of frames from the named stream, returning a list of CameraFrames."""
        return self._dispatch_loop_tasks(
            *(LoopTask.with_request(self._capture_frame, name) for _ in range(n_frames))
        )
