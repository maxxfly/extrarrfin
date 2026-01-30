"""
STRM file creation for streaming mode
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class STRMWriter:
    """Creates STRM files for streaming instead of downloading"""

    @staticmethod
    def create_strm_file(
        youtube_url: str,
        base_filename: str,
        output_directory: Path,
    ) -> Path:
        """
        Create a .strm file containing the YouTube URL

        Args:
            youtube_url: The YouTube video URL
            base_filename: Base filename (without extension)
            output_directory: Directory where the STRM file should be saved

        Returns:
            Path to the created STRM file
        """
        strm_path = output_directory / f"{base_filename}.strm"

        try:
            with open(strm_path, "w", encoding="utf-8") as f:
                f.write(youtube_url)
            logger.info(f"Created STRM file: {strm_path}")
            return strm_path
        except Exception as e:
            logger.error(f"Failed to create STRM file: {e}")
            raise
