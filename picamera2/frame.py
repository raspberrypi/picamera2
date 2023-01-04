from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from picamera2.request import CompletedRequest


@dataclass
class CameraFrame:
    array: np.ndarray
    """The image data as a numpy array."""

    config: dict
    """The configuration used to capture the image."""

    metadata: dict
    """The metadata associated with the image."""

    @classmethod
    def from_request(cls, name: str, request: CompletedRequest) -> CameraFrame:
        """Create a CameraFrame from a CompletedRequest."""
        return cls(
            array=request.make_array(name),
            metadata=request.get_metadata(),
            config=request.config,
        )
