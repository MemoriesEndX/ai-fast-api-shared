class TimestampFormatter:
    """Utility for converting floating-point seconds into MM:SS / HH:MM:SS timestamps."""

    @staticmethod
    def seconds_to_timestamp(seconds: float) -> str:
        """Convert float seconds into formatted timestamp string (MM:SS or HH:MM:SS)."""
        if seconds is None or seconds < 0:
            return "00:00"

        total_sec = int(round(seconds))
        hours = total_sec // 3600
        minutes = (total_sec % 3600) // 60
        secs = total_sec % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    @classmethod
    def format_time_range(cls, start_sec: float, end_sec: float) -> str:
        """Format start and end seconds into range string (e.g. '04:32 - 05:10')."""
        start_str = cls.seconds_to_timestamp(start_sec)
        end_str = cls.seconds_to_timestamp(end_sec)
        return f"{start_str} - {end_str}"
