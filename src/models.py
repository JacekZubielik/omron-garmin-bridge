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

    @staticmethod
    def _bp_grade(systolic: int, diastolic: int) -> int:
        """Return numeric grade for a single axis (WHO/ESC)."""
        sys_grades = [(120, 0), (130, 1), (140, 2), (160, 3), (180, 4)]
        dia_grades = [(80, 0), (85, 1), (90, 2), (100, 3), (110, 4)]
        sys_g = next((g for threshold, g in sys_grades if systolic < threshold), 5)
        dia_g = next((g for threshold, g in dia_grades if diastolic < threshold), 5)
        return max(sys_g, dia_g)

    @property
    def category(self) -> str:
        """Blood pressure category according to WHO/ESC classification.

        Classification uses the HIGHER category of either systolic or diastolic,
        as per WHO/ESC guidelines.
        """
        grade = self._bp_grade(self.systolic, self.diastolic)
        categories = [
            "optimal",
            "normal",
            "high_normal",
            "grade1_hypertension",
            "grade2_hypertension",
            "grade3_hypertension",
        ]
        return categories[grade]

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
