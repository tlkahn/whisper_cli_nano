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
python whisper_to_srt.py audio.mp3
```

### Specify custom output path:
```bash
python whisper_to_srt.py podcast.mp3 subtitles.srt
```

### Use as a Python module:
```python
from whisper_to_srt import convert_to_srt

# Convert with default settings
convert_to_srt("podcast.mp3")

# Specify output path
convert_to_srt("podcast.mp3", "output/subtitles.srt")

# Use custom API key
convert_to_srt("podcast.mp3", api_key="sk-...")
```

## Requirements

- Python 3.10+
- OpenAI API key with access to Whisper API
- Audio file in supported format (MP3, MP4, MPEG, MPGA, M4A, WAV, WEBM)

## Pricing

OpenAI Whisper API pricing is $0.006 per minute of audio (as of 2024).

## License

MIT
