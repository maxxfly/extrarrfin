"""
NFO file creation for Jellyfin/Kodi compatibility
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class NFOWriter:
    """Creates NFO metadata files for media"""

    @staticmethod
    def _escape_xml(text: str) -> str:
        """Escape special XML characters to prevent invalid NFO files"""
        if not text:
            return ""
        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    @staticmethod
    def create_nfo_file(
        base_filename: str,
        output_directory: Path,
        video_info: dict,
        nfo_type: str = "episode",
    ) -> None:
        """
        Create a .nfo file with video metadata for Jellyfin/Kodi compatibility

        Args:
            base_filename: Base filename (without extension)
            output_directory: Directory where the NFO file should be saved
            video_info: Dictionary containing video metadata from yt-dlp
            nfo_type: Type of NFO file - "episode" for episodedetails, "movie" for movie format
        """
        nfo_path = output_directory / f"{base_filename}.nfo"

        # Determine root element based on type
        root_element = "episodedetails" if nfo_type == "episode" else "movie"

        # Escape all text content for XML safety
        title = NFOWriter._escape_xml(video_info.get("title", "Unknown"))
        channel = NFOWriter._escape_xml(video_info.get("channel", ""))
        uploader = NFOWriter._escape_xml(video_info.get("uploader", ""))
        video_id = NFOWriter._escape_xml(video_info.get("id", ""))
        video_url = NFOWriter._escape_xml(
            video_info.get("webpage_url", video_info.get("url", ""))
        )

        try:
            with open(nfo_path, "w", encoding="utf-8") as nfo:
                nfo.write('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n')
                nfo.write(f"<{root_element}>\n")
                nfo.write(f"  <title>{title}</title>\n")
                nfo.write(f"  <originaltitle>{title}</originaltitle>\n")
                nfo.write(f"  <studio>{channel}</studio>\n")
                nfo.write(f"  <director>{uploader}</director>\n")
                nfo.write("  <source>YouTube</source>\n")
                nfo.write(f"  <id>{video_id}</id>\n")
                nfo.write(f"  <youtubeurl>{video_url}</youtubeurl>\n")
                if video_info.get("duration"):
                    nfo.write(f"  <runtime>{video_info['duration'] // 60}</runtime>\n")
                nfo.write(f"</{root_element}>\n")
            logger.info(f"Created NFO file: {nfo_path}")
        except Exception as e:
            logger.warning(f"Failed to create NFO file: {e}")

    @staticmethod
    def extract_video_ids_from_nfo_files(directory: Path) -> set[str]:
        """
        Extract YouTube video IDs from existing NFO files in a directory.

        Args:
            directory: Directory containing NFO files

        Returns:
            Set of YouTube video IDs found in NFO files
        """
        video_ids: set[str] = set()

        if not directory.exists():
            return video_ids

        import re

        id_pattern = re.compile(r"<id>([^<]+)</id>")

        for nfo_file in directory.glob("*.nfo"):
            try:
                content = nfo_file.read_text(encoding="utf-8")
                match = id_pattern.search(content)
                if match:
                    video_id = match.group(1).strip()
                    if video_id:
                        video_ids.add(video_id)
            except Exception as e:
                logger.warning(f"Failed to read NFO file {nfo_file}: {e}")

        return video_ids
