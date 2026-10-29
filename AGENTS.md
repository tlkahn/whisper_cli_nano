# AGENTS.md

Notes for agents working on `whisper-cli-nano`: a thin CLI/module over the OpenAI transcription API.

## Layout

- `src/whisper_cli_nano/__init__.py` - all logic: `convert_to_srt`, `transcribe`, `join_text`, `split_audio_into_chunks`, `compress_audio`, `merge_srt_files`.
- `src/whisper_cli_nano/cli.py` - argparse front end only; keep it free of logic.
- `tests/test_chunking.py` - the one runnable check. No fixtures, no network.

## Commands

```bash
uv run --project . python tests/test_chunking.py          # must print "self-check ok"
uv run --project . whisper-to-srt --help
uv run --project . whisper-to-srt in.mp3 out.srt --chunk-seconds 130 --model whisper-1
```

`uv run` may rewrite the `source =` URLs in `uv.lock` to the local PyPI mirror. That diff is noise, revert it (`git checkout uv.lock`) before committing.

## API constraints that shape the code

- **`whisper-1` is the only model that returns timestamps.** It accepts `response_format` values including `srt` / `verbose_json`. `gpt-4o-transcribe` and `gpt-4o-mini-transcribe` accept only `json` / `text`, so sending `srt` is a 400. `SRT_MODELS` in `__init__.py` is the single place that decides this, and the output extension (`.srt` vs `.txt`) follows it. Do not hardcode a format anywhere else.
- **Long single requests truncate silently.** A 10.5 minute mp3 (8.3MB) sent in one `gpt-4o-transcribe` call returned HTTP 200 with 2485 chars, stopping about three quarters of the way through the audio. The same audio in 5 chunks of 130s returned 3858 chars and covered the whole file. Nothing in the response signals the cut.
- **The 25MB limit is not the only reason to chunk.** Size-based chunking alone is unsafe: files under 25MB still hit the truncation above. Chunk for duration as well, around 120-180s per chunk.
- **`whisper-1` does not truncate but degrades.** Same audio, non-chunked: complete transcript, but the Chinese output had no punctuation at all, terms came out mangled (`Kiefer` for kefir, `Sephoraphane` for sulforaphane, `氟酸` for folate, `卡路里` for "carbs"), and phrases were dropped (`一個就是然後一個就是`, where the speaker named IL-6 and TNF-alpha). A `prompt` with punctuated text plus the expected proper nouns fixes most of this.
- **The prompt must be re-sent with every chunk.** Term spellings are decided per request, so a prompt only on chunk 1 gives kefir in one chunk and Kiefer in the next. `convert_to_srt` passes `prompt` and `language` to every `transcribe` call for this reason.
- **`language` is worth setting.** Autodetect on Traditional Chinese produced mixed output and English loanwords written out phonetically.
- **Always send real chunk files.** A zero-length or sub-second chunk is rejected with `400 Audio file might be corrupted or unsupported`. `split_audio_into_chunks` now probes each chunk and drops anything under 1s, which covers the stub produced at the end of a split.

## Chunking rules

- Split with explicit `ffmpeg -ss START -t DURATION -i in.mp3` re-encoded to mono 16kHz 64kbps. Roughly 1MB per 130s.
- Do not split with the `segment` muxer (`-f segment -segment_time ...`). Combined with a re-encode it left a final 0.06s / 2924 byte file that the API rejected, even though the same parameters worked for the earlier chunks.
- `merge_srt_files` must receive offsets of `i * chunk_seconds`, the requested duration, not the measured duration of each chunk. Chunks are not exactly the requested length.
- Text chunks are stitched by `join_text`, which inserts a space only when neither edge is a CJK character. Do not add `\n\n` between chunks: it breaks mid-sentence prose and mid-paragraph flow.

## Verification

Neither the API nor the SDK reports truncation, so check output shape after any model or chunking change:

- Characters per second of audio: Chinese lands around 5-7, English around 12-18 per second. Far below that means a cut.
- The last chunk's text should contain the tail of the audio (the outro, the final word). If it stops mid-sentence, the request was truncated or a chunk was dropped.
- For SRT, confirm timestamps in the second chunk are offset by `chunk_seconds`, not near zero.

`tests/test_chunking.py` covers format selection per model (and that empty options are not sent), the CJK spacing rule, and SRT offset arithmetic. Extend it, do not replace it with a heavier harness.

## Style

- Stdlib and `openai` only. Do not add dependencies for CLI parsing, audio splitting, or SRT handling.
- Keep public API changes backwards compatible: `convert_to_srt(path)` and `convert_to_srt(path, out)` must keep working.
- Raise `RuntimeError` with the ffmpeg stderr attached for subprocess failures, and clean up temp files in a `finally` block, as `convert_to_srt` does.
