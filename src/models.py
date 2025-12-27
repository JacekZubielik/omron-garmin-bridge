"""Data models for Omron Garmin Bridge."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class BloodPressureReading:
    """Blood pressure measurement from OMRON device."""

    timestamp: datetime
    systolic: int  # mmHg - systolic pressure
    diastolic: int  # mmHg - diastolic pressure
    pulse: int  # bpm - heart rate
    irregular_heartbeat: bool = False  # IHB flag
    body_movement: bool = False  # MOV flag
    user_slot: int = 1  # User slot in device (1 or 2)

    @property
    def record_hash(self) -> str:
        """Unique hash for deduplication."""
        return (
            f"{self.timestamp.isoformat()}_"
            f"{self.systolic}_{self.diastolic}_{self.pulse}_{self.user_slot}"
        )

    @property
    def category(self) -> str:
        """Blood pressure category according to WHO/ESC classification."""
        if self.systolic < 120 and self.diastolic < 80:
            return "optimal"
        elif self.systolic < 130 and self.diastolic < 85:
            return "normal"
        elif self.systolic < 140 and self.diastolic < 90:
            return "high_normal"
        elif self.systolic < 160 and self.diastolic < 100:
            return "grade1_hypertension"
        elif self.systolic < 180 and self.diastolic < 110:
            return "grade2_hypertension"
        else:
            return "grade3_hypertension"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "systolic": self.systolic,
            "diastolic": self.diastolic,
            "pulse": self.pulse,
            "category": self.category,
            "irregular_heartbeat": self.irregular_heartbeat,
            "body_movement": self.body_movement,
            "user_slot": self.user_slot,
        }

    def __str__(self) -> str:
        """Human-readable representation."""
        return (
            f"BP: {self.systolic}/{self.diastolic} mmHg, "
            f"Pulse: {self.pulse} bpm, "
            f"Category: {self.category}"
        )
