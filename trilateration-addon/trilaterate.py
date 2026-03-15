"""
WiFi CSI Trilateration Engine - Pure NumPy implementation
Based on Espressif esp-csi (Apache 2.0)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger(__name__)

PATH_LOSS_EXPONENT = 2.7
RSSI_AT_1M = -45
KALMAN_Q = 0.1
KALMAN_R = 2.0


@dataclass
class Anchor:
    node_id: str
    x: float
    y: float
    rssi_history: list = field(default_factory=list)
    history_size: int = 5

    def add_rssi(self, rssi: float):
        self.rssi_history.append(rssi)
        if len(self.rssi_history) > self.history_size:
            self.rssi_history.pop(0)

    @property
    def smoothed_rssi(self) -> Optional[float]:
        if not self.rssi_history:
            return None
        return float(np.mean(self.rssi_history))

    @property
    def estimated_distance(self) -> Optional[float]:
        rssi = self.smoothed_rssi
        if rssi is None:
            return None
        return max(0.1, 10 ** ((RSSI_AT_1M - rssi) / (10 * PATH_LOSS_EXPONENT)))


class KalmanFilter2D:
    def __init__(self):
        self.x = np.zeros(4)
        self.P = np.eye(4) * 100
        dt = 0.1
        self.F = np.array([[1,0,dt,0],[0,1,0,dt],[0,0,1,0],[0,0,0,1]], dtype=float)
        self.H = np.array([[1,0,0,0],[0,1,0,0]], dtype=float)
        self.Q = np.eye(4) * KALMAN_Q
        self.R = np.eye(2) * KALMAN_R
        self.initialized = False

    def update(self, x: float, y: float) -> tuple:
        z = np.array([x, y])
        if not self.initialized:
            self.x[0], self.x[1] = x, y
            self.initialized = True
            return x, y
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        y_inn = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y_inn
        self.P = (np.eye(4) - K @ self.H) @ self.P
        return float(self.x[0]), float(self.x[1])


class Trilaterator:
    def __init__(self, room_width: float, room_height: float):
        self.anchors: dict = {}
        self.room_width = room_width
        self.room_height = room_height
        self.kalman = KalmanFilter2D()

    def add_anchor(self, node_id: str, x: float, y: float):
        self.anchors[node_id] = Anchor(node_id=node_id, x=x, y=y)
        logger.info(f"Anchor registered: {node_id} at ({x}, {y})")

    def update_rssi(self, node_id: str, rssi: float):
        if node_id not in self.anchors:
            logger.warning(f"Unknown anchor: {node_id}")
            return
        self.anchors[node_id].add_rssi(rssi)

    def compute_position(self) -> Optional[dict]:
        active = [a for a in self.anchors.values() if a.estimated_distance is not None]
        if len(active) < 3:
            return None

        # Least squares trilateration using pure numpy
        # Convert to linear system using anchor[0] as reference
        ref = active[0]
        A, b = [], []
        for a in active[1:]:
            A.append([
                2 * (a.x - ref.x),
                2 * (a.y - ref.y)
            ])
            b.append(
                a.estimated_distance**2 - ref.estimated_distance**2
                - a.x**2 + ref.x**2
                - a.y**2 + ref.y**2
            )

        A = np.array(A)
        b = np.array(b)

        try:
            result, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
            raw_x, raw_y = result
        except Exception:
            return None

        # Clamp to room bounds
        raw_x = float(np.clip(raw_x, 0, self.room_width))
        raw_y = float(np.clip(raw_y, 0, self.room_height))

        smooth_x, smooth_y = self.kalman.update(raw_x, raw_y)

        # Confidence based on residual
        predicted = np.sqrt(np.sum((np.array([[a.x, a.y] for a in active]) - [smooth_x, smooth_y])**2, axis=1))
        actual = np.array([a.estimated_distance for a in active])
        residual = float(np.mean(np.abs(predicted - actual)))
        confidence = max(0, min(100, int(100 - residual * 15)))

        return {
            "x": round(smooth_x, 2),
            "y": round(smooth_y, 2),
            "confidence": confidence,
            "active_anchors": len(active),
            "anchor_distances": {a.node_id: round(a.estimated_distance, 2) for a in active}
        }
