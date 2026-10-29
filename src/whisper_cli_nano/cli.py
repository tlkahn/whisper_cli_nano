#!/usr/bin/env python3
"""CLI entry point for whisper-cli-nano."""

import argparse
import sys
from whisper_cli_nano import convert_to_srt


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="whisper-to-srt",
        description="Transcribe audio with OpenAI (SRT for whisper-1, plain text otherwise).",
    )
    parser.add_argument("audio_file")
    parser.add_argument("output_file", nargs="?")
    parser.add_argument("--chunk-seconds", type=int, default=None,
                        help="Split the audio into chunks of this many seconds. "
                             "Use this for long files: a single multi-minute request can "
                             "come back silently truncated.")
    parser.add_argument("--model", default="whisper-1",
                        help="whisper-1 (SRT) or gpt-4o-transcribe / gpt-4o-mini-transcribe (text)")
    parser.add_argument("--prompt", default=None,
                        help="Vocabulary and context hint, re-sent with every chunk")
    parser.add_argument("--language", default=None, help="Language code, e.g. zh, en")
    args = parser.parse_args()

    try:
        convert_to_srt(
            args.audio_file,
            args.output_file,
            chunk_seconds=args.chunk_seconds,
            model=args.model,
            prompt=args.prompt,
            language=args.language,
        )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
