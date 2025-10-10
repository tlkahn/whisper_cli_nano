#!/usr/bin/env python3
"""CLI entry point for whisper-cli-nano."""

import sys
from whisper_cli_nano import convert_to_srt


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: whisper-to-srt <audio_file> [output_file]")
        print("\nExample:")
        print("  whisper-to-srt podcast.mp3")
        print("  whisper-to-srt podcast.mp3 subtitles.srt")
        sys.exit(1)

    audio_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        convert_to_srt(audio_path, output_path)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
