from __future__ import annotations

import array
import threading
import wave
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class WavRecorder:
    """Thread-safe PCM int16 WAV recorder for ROS Int16MultiArray audio."""

    def __init__(self, output_dir: str = "recordings") -> None:
        self._output_dir = Path(output_dir)
        self._lock = threading.RLock()
        self._wav: Optional[wave.Wave_write] = None
        self._path: Optional[Path] = None
        self._topic: Optional[str] = None
        self._channels = 0
        self._sample_rate = 0
        self._frames_written = 0
        self._started_at: Optional[datetime] = None
        self._paused = False

    def start(self, topic: str, channels: int, sample_rate: int) -> dict:
        with self._lock:
            if self._wav is not None:
                raise RuntimeError(f"recording already active: {self._path}")

            self._output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_topic = topic.strip("/").replace("/", "_") or "mic"
            path = self._output_dir / f"{timestamp}_{safe_topic}.wav"

            wav = wave.open(str(path), "wb")
            wav.setnchannels(channels)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)

            self._wav = wav
            self._path = path
            self._topic = topic
            self._channels = channels
            self._sample_rate = sample_rate
            self._frames_written = 0
            self._started_at = datetime.now()
            self._paused = False
            return self.status()

    def write_msg(self, topic: str, msg: Any) -> None:
        with self._lock:
            if self._wav is None or self._paused or topic != self._topic:
                return
            pcm = array.array("h", msg.data)
            self._wav.writeframes(pcm.tobytes())
            if self._channels > 0:
                self._frames_written += len(pcm) // self._channels

    def pause(self) -> dict:
        with self._lock:
            if self._wav is None:
                raise RuntimeError("recording is not active")
            self._paused = True
            return self.status()

    def resume(self) -> dict:
        with self._lock:
            if self._wav is None:
                raise RuntimeError("recording is not active")
            self._paused = False
            return self.status()

    def stop(self) -> dict:
        with self._lock:
            if self._wav is None:
                raise RuntimeError("recording is not active")
            status = self.status()
            self._wav.close()
            self._wav = None
            self._path = None
            self._topic = None
            self._channels = 0
            self._sample_rate = 0
            self._frames_written = 0
            self._started_at = None
            self._paused = False
            return status

    def status(self) -> dict:
        active = self._wav is not None
        duration = 0.0
        if self._sample_rate > 0:
            duration = self._frames_written / self._sample_rate
        return {
            "active": active,
            "paused": self._paused if active else False,
            "path": str(self._path) if self._path is not None else None,
            "topic": self._topic,
            "channels": self._channels if active else None,
            "sample_rate": self._sample_rate if active else None,
            "frames_written": self._frames_written,
            "duration_sec": duration,
            "started_at": self._started_at.isoformat() if self._started_at else None,
        }
