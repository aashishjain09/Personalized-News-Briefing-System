"""Time utilities for timestamp handling and scheduling."""

from datetime import datetime, timedelta, timezone
from typing import Optional


class TimeUtility:
    """Handles timestamp generation and timezone conversions."""

    UTC = timezone.utc

    @staticmethod
    def now_utc() -> datetime:
        """
        Get current time in UTC.

        Returns:
            Timezone-aware datetime in UTC
        """
        return datetime.now(tz=TimeUtility.UTC)

    @staticmethod
    def timestamp_utc(dt: Optional[datetime] = None) -> str:
        """
        Convert datetime to ISO 8601 UTC string.

        Args:
            dt: Datetime to convert (default: now)

        Returns:
            ISO 8601 formatted string (e.g., '2024-01-15T10:30:45.123456+00:00')
        """
        if dt is None:
            dt = TimeUtility.now_utc()

        # Ensure timezone-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TimeUtility.UTC)

        return dt.isoformat()

    @staticmethod
    def parse_timestamp(timestamp_str: str) -> datetime:
        """
        Parse ISO 8601 timestamp string to datetime.

        Args:
            timestamp_str: ISO 8601 formatted string

        Returns:
            Timezone-aware datetime object

        Raises:
            ValueError: If timestamp format is invalid
        """
        try:
            # Try parsing with timezone
            return datetime.fromisoformat(timestamp_str)
        except ValueError:
            # Try parsing without timezone, assume UTC
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt if dt.tzinfo else dt.replace(tzinfo=TimeUtility.UTC)

    @staticmethod
    def days_ago(days: int) -> datetime:
        """
        Get datetime for N days in the past.

        Args:
            days: Number of days to go back

        Returns:
            Timezone-aware datetime (UTC)
        """
        return TimeUtility.now_utc() - timedelta(days=days)

    @staticmethod
    def hours_ago(hours: int) -> datetime:
        """
        Get datetime for N hours in the past.

        Args:
            hours: Number of hours to go back

        Returns:
            Timezone-aware datetime (UTC)
        """
        return TimeUtility.now_utc() - timedelta(hours=hours)

    @staticmethod
    def minutes_ago(minutes: int) -> datetime:
        """
        Get datetime for N minutes in the past.

        Args:
            minutes: Number of minutes to go back

        Returns:
            Timezone-aware datetime (UTC)
        """
        return TimeUtility.now_utc() - timedelta(minutes=minutes)

    @staticmethod
    def is_within_window(timestamp: datetime, hours: int) -> bool:
        """
        Check if timestamp is within N hours of now.

        Args:
            timestamp: Timestamp to check
            hours: Time window in hours

        Returns:
            True if timestamp is within the last N hours
        """
        # Ensure timezone-aware comparison
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=TimeUtility.UTC)

        cutoff = TimeUtility.hours_ago(hours)
        return timestamp >= cutoff
