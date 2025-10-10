"""
Whisper MP3 to SRT Converter
A minimal, elegant CLI tool to convert audio files to SRT subtitles using OpenAI's Whisper API.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List
from openai import OpenAI

__version__ = "0.1.0"

# OpenAI Whisper API file size limit (25MB)
MAX_FILE_SIZE = 25 * 1024 * 1024
# Target chunk duration in seconds (10 minutes = 600s)
CHUNK_DURATION = 600


def get_audio_duration(audio_file: str) -> float:
    """
    Get the duration of an audio file in seconds.

    Args:
        audio_file: Path to the audio file

    Returns:
        Duration in seconds
    """
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            audio_file
        ], check=True, capture_output=True, text=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError) as e:
        raise RuntimeError(f"Failed to get audio duration: {e}")


def split_audio_into_chunks(input_file: str, chunk_duration: int = CHUNK_DURATION) -> List[str]:
    """
    Split audio file into chunks of specified duration.

    Args:
        input_file: Path to the input audio file
        chunk_duration: Duration of each chunk in seconds

    Returns:
        List of paths to chunk files
    """
    duration = get_audio_duration(input_file)
    num_chunks = int(duration / chunk_duration) + (1 if duration % chunk_duration > 0 else 0)

    print(f"Splitting audio into {num_chunks} chunks ({chunk_duration}s each)...")

    chunk_files = []
    for i in range(num_chunks):
        start_time = i * chunk_duration
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            chunk_path = tmp.name

        try:
            subprocess.run([
                'ffmpeg', '-i', input_file,
                '-ss', str(start_time),
                '-t', str(chunk_duration),
                '-b:a', '64k',
                '-ar', '16000',
                '-ac', '1',
                '-y',
                chunk_path
            ], check=True, capture_output=True, text=True)

            chunk_files.append(chunk_path)
            print(f"  Created chunk {i+1}/{num_chunks}")
        except subprocess.CalledProcessError as e:
            # Clean up on failure
            for cf in chunk_files:
                if os.path.exists(cf):
                    os.unlink(cf)
            if os.path.exists(chunk_path):
                os.unlink(chunk_path)
            raise RuntimeError(f"Failed to split audio: {e.stderr}")

    return chunk_files


def parse_srt_timestamp(timestamp: str) -> float:
    """Convert SRT timestamp to seconds (e.g., '00:01:23,456' -> 83.456)"""
    match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', timestamp)
    if not match:
        return 0.0
    hours, minutes, seconds, milliseconds = map(int, match.groups())
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000


def format_srt_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format (e.g., 83.456 -> '00:01:23,456')"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def merge_srt_files(srt_contents: List[str], time_offsets: List[float]) -> str:
    """
    Merge multiple SRT contents with time offsets.

    Args:
        srt_contents: List of SRT file contents
        time_offsets: List of time offsets in seconds for each chunk

    Returns:
        Merged SRT content
    """
    merged = []
    subtitle_counter = 1

    for srt_content, offset in zip(srt_contents, time_offsets):
        if not srt_content.strip():
            continue

        # Parse each subtitle block
        blocks = re.split(r'\n\n+', srt_content.strip())

        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue

            # Extract timestamp line (format: "00:00:00,000 --> 00:00:05,000")
            timestamp_line = lines[1]
            match = re.match(r'(\S+)\s+-->\s+(\S+)', timestamp_line)
            if not match:
                continue

            start_ts, end_ts = match.groups()

            # Parse and adjust timestamps
            start_seconds = parse_srt_timestamp(start_ts) + offset
            end_seconds = parse_srt_timestamp(end_ts) + offset

            # Format adjusted timestamps
            new_start = format_srt_timestamp(start_seconds)
            new_end = format_srt_timestamp(end_seconds)

            # Rebuild the subtitle block with new counter and timestamps
            merged.append(f"{subtitle_counter}")
            merged.append(f"{new_start} --> {new_end}")
            merged.extend(lines[2:])  # Add subtitle text
            merged.append("")  # Empty line between blocks

            subtitle_counter += 1

    return '\n'.join(merged)


def compress_audio(input_file: Path) -> str:
    """
    Compress audio file to reduce size while maintaining quality for speech recognition.

    Args:
        input_file: Path to the input audio file

    Returns:
        Path to the compressed temporary file
    """
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        print(f"Compressing audio file (original size: {input_file.stat().st_size / (1024*1024):.1f}MB)...")
        subprocess.run([
            'ffmpeg', '-i', str(input_file),
            '-b:a', '64k',      # Lower bitrate for smaller size
            '-ar', '16000',     # 16kHz sample rate (optimal for Whisper)
            '-ac', '1',         # Mono audio (speech doesn't need stereo)
            '-y',               # Overwrite output file
            tmp_path
        ], check=True, capture_output=True, text=True)

        compressed_size = os.path.getsize(tmp_path)
        print(f"Compressed to {compressed_size / (1024*1024):.1f}MB")
        return tmp_path
    except subprocess.CalledProcessError as e:
        os.unlink(tmp_path)
        raise RuntimeError(f"Audio compression failed: {e.stderr}") from e
    except FileNotFoundError:
        os.unlink(tmp_path)
        raise RuntimeError("ffmpeg not found. Please install ffmpeg: https://ffmpeg.org/download.html")


def convert_to_srt(audio_path: str, output_path: str | None = None, api_key: str | None = None) -> str:
    """
    Convert an audio file to SRT format using OpenAI's Whisper API.

    Args:
        audio_path: Path to the audio file (mp3, mp4, mpeg, mpga, m4a, wav, or webm)
        output_path: Optional output path for the SRT file (defaults to same name as input)
        api_key: Optional OpenAI API key (defaults to OPENAI_API_KEY env var)

    Returns:
        Path to the generated SRT file
    """
    audio_file = Path(audio_path)

    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Initialize OpenAI client
    client = OpenAI(api_key=api_key) if api_key else OpenAI()

    # Determine output path
    if output_path is None:
        output_path = audio_file.with_suffix('.srt')
    else:
        output_path = Path(output_path)

    print(f"Converting {audio_file.name} to SRT format...")

    # Check file size and compress if necessary
    file_size = audio_file.stat().st_size
    compressed_file = None
    chunk_files = []

    try:
        # First, try compression if file is large
        if file_size > MAX_FILE_SIZE:
            compressed_file = compress_audio(audio_file)
            file_to_process = compressed_file
        else:
            file_to_process = str(audio_file)

        # Check if we still need to split after compression
        processed_size = os.path.getsize(file_to_process)

        if processed_size <= MAX_FILE_SIZE:
            # File is small enough, transcribe directly
            with open(file_to_process, 'rb') as audio:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio,
                    response_format="srt"
                )
        else:
            # File is still too large, split into chunks
            chunk_files = split_audio_into_chunks(file_to_process)

            print(f"Transcribing {len(chunk_files)} chunks...")
            srt_contents = []
            time_offsets = []

            for i, chunk_file in enumerate(chunk_files):
                print(f"  Transcribing chunk {i+1}/{len(chunk_files)}...")

                with open(chunk_file, 'rb') as audio:
                    chunk_transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio,
                        response_format="srt"
                    )

                srt_contents.append(chunk_transcript)
                time_offsets.append(i * CHUNK_DURATION)

            print("Merging transcripts...")
            transcript = merge_srt_files(srt_contents, time_offsets)

        # Write the SRT content to file
        output_path.write_text(transcript)

        print(f"✓ Successfully created: {output_path}")
        return str(output_path)

    finally:
        # Clean up temporary files
        if compressed_file and os.path.exists(compressed_file):
            os.unlink(compressed_file)

        for chunk_file in chunk_files:
            if os.path.exists(chunk_file):
                os.unlink(chunk_file)


__all__ = ["convert_to_srt"]
