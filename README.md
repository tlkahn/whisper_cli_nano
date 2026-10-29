# Whisper MP3 to SRT Converter

A minimal, elegant CLI tool to convert audio files to SRT subtitle format using OpenAI's Whisper API.

## Features

- Convert audio files (MP3, MP4, MPEG, MPGA, M4A, WAV, WEBM) to SRT subtitles
- Clean, simple Python implementation
- Uses OpenAI's official Whisper API
- Automatic timestamp generation

## Installation

1. Clone this repository or download the files

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your OpenAI API key:
```bash
export OPENAI_API_KEY='your-api-key-here'
```

Or create a `.env` file:
```bash
cp .env.example .env
# Edit .env and add your API key
```

## Usage

### Basic usage (output will be saved as `audio.srt`):
```bash
whisper-to-srt audio.mp3
```

### Specify custom output path:
```bash
whisper-to-srt podcast.mp3 subtitles.srt
```

### Long files, other models, language and vocabulary hints:
```bash
whisper-to-srt lecture.mp4 lecture.txt \
  --chunk-seconds 130 \
  --model gpt-4o-transcribe \
  --language zh \
  --prompt "繁體中文，加上標點。專有名詞：inflammaging、TNF-α、plantain。"
```

Pass `--chunk-seconds` for anything longer than a few minutes. A single request for
ten minutes of audio can return HTTP 200 with a transcript that stops early; chunking
bounds the request and makes truncation visible per chunk. The same `--prompt` is sent
with every chunk, which keeps spellings of names and terms consistent across boundaries.

`--model whisper-1` returns SRT with timestamps. `gpt-4o-transcribe` and
`gpt-4o-mini-transcribe` return plain text (no timestamps are available), so chunks are
concatenated as prose and the default output extension becomes `.txt`.

### Use as a Python module:
```python
from whisper_cli_nano import convert_to_srt

# Convert with default settings
convert_to_srt("podcast.mp3")

# Specify output path
convert_to_srt("podcast.mp3", "output/subtitles.srt")

# Force chunking, pick a model, hint language and vocabulary
convert_to_srt("lecture.mp4", "lecture.txt", chunk_seconds=130,
               model="gpt-4o-transcribe", language="zh", prompt="proper nouns here")

# Use custom API key
convert_to_srt("podcast.mp3", api_key="sk-...")
```

## Testing

```bash
uv run --project . python tests/test_chunking.py
```

## Requirements

- Python 3.10+
- OpenAI API key with access to Whisper API
- Audio file in supported format (MP3, MP4, MPEG, MPGA, M4A, WAV, WEBM)

## Pricing

OpenAI Whisper API pricing is $0.006 per minute of audio (as of 2024).

## License

MIT
