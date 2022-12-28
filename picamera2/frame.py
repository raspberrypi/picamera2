from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from picamera2.request import CompletedRequest


@dataclass
class CameraFrame:
    array: np.ndarray

    config: dict

    metadata: dict

    @classmethod
    def from_request(cls, name: str, request: CompletedRequest) -> CameraFrame:
        return cls(
            array=request.make_array(name),
            metadata=request.get_metadata(),
            config=request.config,
        )
