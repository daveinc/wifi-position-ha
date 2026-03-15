"""
WiFi CSI Trilateration Engine
Based on Espressif esp-csi (Apache 2.0)
https://github.com/espressif/esp-csi

Converts RSSI readings from fixed ESP32 anchor nodes
into X/Y position coordinates using weighted least squares trilateration.
"""

import numpy as np
from scipy.optimize import minimize
from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Path loss model constants
# Tuned for 2.4GHz indoor environments
PATH_LOSS_EXPONENT = 2.7       # Indoor: typically 2.5–3.5
RSSI_AT_1M = -45               # Calibrate per environment (dBm at 1 meter)
KALMAN_Q = 0.1                 # Process noise — higher = follows movement faster
KALMAN_R = 2.0                 # Measurement noise — higher = smoother but slower


@dataclass
class Anchor:
    """
    A fixed ESP32 node at a known position in the room.
    Receives CSI/RSSI from the beacon carried by the tracked person.
    """
    node_id: str
    x: float
    y: float
    rssi_history: list = field(default_factory=list)
    history_size: int = 5       # Rolling average window

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
        """Convert smoothed RSSI to distance in meters using log-distance path loss model."""
        rssi = self.smoothed_rssi
        if rssi is None:
            return None
        distance = 10 ** ((RSSI_AT_1M - rssi) / (10 * PATH_LOSS_EXPONENT))
        return max(0.1, distance)  # clamp to minimum 10cm


class KalmanFilter2D:
    """
    Simple 2D Kalman filter to smooth position output.
    Removes jitter from noisy RSSI readings.
    """
    def __init__(self):
        self.x = np.zeros(4)             # [x, y, vx, vy]
        self.P = np.eye(4) * 100         # Initial uncertainty — high = trusts measurements more at start
        dt = 0.1                          # 100ms update rate
        self.F = np.array([              # State transition matrix
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1,  0],
            [0, 0, 0,  1]
        ])
        self.H = np.array([              # Measurement matrix (we only observe x,y)
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ])
        self.Q = np.eye(4) * KALMAN_Q    # Process noise
        self.R = np.eye(2) * KALMAN_R    # Measurement noise
        self.initialized = False

    def update(self, x: float, y: float) -> tuple[float, float]:
        z = np.array([x, y])

        if not self.initialized:
            self.x[0] = x
            self.x[1] = y
            self.initialized = True
            return x, y

        # Predict
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q

        # Update
        y_innov = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y_innov
        self.P = (np.eye(4) - K @ self.H) @ self.P

        return float(self.x[0]), float(self.x[1])


class Trilaterator:
    """
    Main positioning engine.
    Takes RSSI readings from 3+ anchors and outputs X/Y coordinates.
    """
    def __init__(self, room_width: float, room_height: float):
        self.anchors: dict[str, Anchor] = {}
        self.room_width = room_width
        self.room_height = room_height
        self.kalman = KalmanFilter2D()
        self.last_position: Optional[tuple[float, float]] = None

    def add_anchor(self, node_id: str, x: float, y: float):
        self.anchors[node_id] = Anchor(node_id=node_id, x=x, y=y)
        logger.info(f"Anchor registered: {node_id} at ({x}, {y})")

    def update_rssi(self, node_id: str, rssi: float):
        if node_id not in self.anchors:
            logger.warning(f"Unknown anchor: {node_id}")
            return
        self.anchors[node_id].add_rssi(rssi)

    def compute_position(self) -> Optional[dict]:
        """
        Run weighted least squares trilateration across all anchors
        that have recent RSSI readings.
        Returns dict with x, y, confidence, and per-anchor distances.
        """
        active = [
            a for a in self.anchors.values()
            if a.estimated_distance is not None
        ]

        if len(active) < 3:
            logger.debug(f"Only {len(active)} active anchors — need at least 3")
            return None

        # Build arrays for optimization
        positions = np.array([[a.x, a.y] for a in active])
        distances = np.array([a.estimated_distance for a in active])

        # Weight by inverse distance squared — closer anchors are more reliable
        weights = 1.0 / (distances ** 2)

        def cost(point):
            diffs = np.sqrt(np.sum((positions - point) ** 2, axis=1)) - distances
            return np.sum(weights * diffs ** 2)

        # Initial guess: weighted centroid
        x0 = np.average(positions[:, 0], weights=weights)
        y0 = np.average(positions[:, 1], weights=weights)

        result = minimize(
            cost,
            x0=[x0, y0],
            method='L-BFGS-B',
            bounds=[(0, self.room_width), (0, self.room_height)]
        )

        if not result.success:
            logger.warning("Trilateration optimization failed")
            return None

        raw_x, raw_y = result.x
        smooth_x, smooth_y = self.kalman.update(raw_x, raw_y)

        # Confidence: based on residual error normalized to room size
        residual = result.fun / len(active)
        confidence = max(0, min(100, int(100 - (residual * 10))))

        self.last_position = (smooth_x, smooth_y)

        return {
            "x": round(smooth_x, 2),
            "y": round(smooth_y, 2),
            "confidence": confidence,
            "active_anchors": len(active),
            "anchor_distances": {
                a.node_id: round(a.estimated_distance, 2)
                for a in active
            }
        }
