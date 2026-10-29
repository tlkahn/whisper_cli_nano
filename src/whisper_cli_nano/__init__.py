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
# Default chunk duration in seconds (10 minutes = 600s)
CHUNK_DURATION = 600
# Only whisper-1 can return timestamped subtitles; the gpt-4o transcribe models
# answer in json/text and are rejected with response_format=srt.
SRT_MODELS = ("whisper-1",)
CJK = re.compile(r"[\u3400-\u9fff]")


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

            # A short tail stub is rejected by the API as "corrupted or unsupported".
            if get_audio_duration(chunk_path) < 1:
                os.unlink(chunk_path)
                continue

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


def transcribe(client, path: str, model: str = "whisper-1",
               prompt: str | None = None, language: str | None = None) -> str:
    """Transcribe one file, choosing a response format the model supports."""
    options = {}
    if prompt:
        options["prompt"] = prompt
    if language:
        options["language"] = language

    with open(path, "rb") as audio:
        result = client.audio.transcriptions.create(
            model=model,
            file=audio,
            response_format="srt" if model in SRT_MODELS else "text",
            **options,
        )
    return result if isinstance(result, str) else result.text


def join_text(parts: List[str]) -> str:
    """Concatenate plain-text chunk transcripts, spacing only between non-CJK edges."""
    joined = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if joined and not (CJK.match(joined[-1]) or CJK.match(part[0])):
            joined += " "
        joined += part
    return joined + "\n"


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


def convert_to_srt(audio_path: str, output_path: str | None = None, api_key: str | None = None,
                   chunk_seconds: int | None = None, model: str = "whisper-1",
                   prompt: str | None = None, language: str | None = None) -> str:
    """
    Convert an audio file to subtitles using OpenAI's transcription API.

    Args:
        audio_path: Path to the audio file (mp3, mp4, mpeg, mpga, m4a, wav, or webm)
        output_path: Optional output path (defaults to same name as input, .srt or .txt)
        api_key: Optional OpenAI API key (defaults to OPENAI_API_KEY env var)
        chunk_seconds: Split into chunks of this length even for small files.
            Long single requests can come back silently truncated, so pass this
            for anything beyond a few minutes. Defaults to only chunking when
            the file exceeds the 25MB request limit.
        model: whisper-1 (returns SRT) or a gpt-4o transcribe model (returns text)
        prompt: Vocabulary/context hint, re-sent with every chunk to keep names consistent
        language: ISO-639-1 language code, e.g. "zh"

    Returns:
        Path to the generated subtitle file
    """
    audio_file = Path(audio_path)

    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Initialize OpenAI client
    client = OpenAI(api_key=api_key) if api_key else OpenAI()

    # Determine output path
    subtitles = model in SRT_MODELS
    if output_path is None:
        output_path = audio_file.with_suffix('.srt' if subtitles else '.txt')
    else:
        output_path = Path(output_path)

    print(f"Converting {audio_file.name} to {'SRT' if subtitles else 'text'} with {model}...")

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

        chunk_duration = chunk_seconds or CHUNK_DURATION

        if chunk_seconds is None and os.path.getsize(file_to_process) <= MAX_FILE_SIZE:
            # File is small enough and chunking was not requested
            transcript = transcribe(client, file_to_process, model, prompt, language)
        else:
            # Split, transcribe each chunk, then stitch timestamps or text back together
            chunk_files = split_audio_into_chunks(file_to_process, chunk_duration)

            print(f"Transcribing {len(chunk_files)} chunks...")
            chunk_contents = []

            for i, chunk_file in enumerate(chunk_files):
                print(f"  Transcribing chunk {i+1}/{len(chunk_files)}...")
                chunk_contents.append(transcribe(client, chunk_file, model, prompt, language))

            print("Merging transcripts...")
            transcript = (merge_srt_files(chunk_contents, [i * chunk_duration for i in range(len(chunk_contents))])
                          if subtitles else join_text(chunk_contents))

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


__all__ = ["convert_to_srt", "transcribe", "join_text"]
