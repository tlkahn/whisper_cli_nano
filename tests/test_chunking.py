"""One runnable check for the chunking/stitching logic. Run: python tests/test_chunking.py"""
import tempfile
import types

from whisper_cli_nano import join_text, merge_srt_files, transcribe


def fake_client(reply="ok"):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return reply

    client = types.SimpleNamespace(
        audio=types.SimpleNamespace(
            transcriptions=types.SimpleNamespace(create=create)
        )
    )
    return client, calls


def test_response_format_follows_model():
    with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
        f.write(b"x")
        f.flush()

        client, calls = fake_client()
        assert transcribe(client, f.name, "whisper-1") == "ok"
        assert calls[0]["response_format"] == "srt"
        assert "prompt" not in calls[0], "empty options must not be sent"

        client, calls = fake_client()
        transcribe(client, f.name, "gpt-4o-transcribe", prompt="names", language="zh")
        assert calls[0]["response_format"] == "text"
        assert calls[0]["prompt"] == "names"
        assert calls[0]["language"] == "zh"


def test_join_text_spacing():
    assert join_text(["你好", "世界。"]) == "你好世界。\n"
    assert join_text(["Hello", "world."]) == "Hello world.\n"
    assert join_text(["你好", " world."]) == "你好world.\n"  # CJK edge: no space inserted
    assert join_text(["", "  "]) == "\n"


def test_merge_offsets_shift_timestamps():
    chunk = "1\n00:00:01,000 --> 00:00:02,000\nhi\n"
    merged = merge_srt_files([chunk, chunk], [0, 120])
    assert "00:02:01,000 --> 00:02:02,000" in merged
    assert merged.count("-->") == 2


if __name__ == "__main__":
    test_response_format_follows_model()
    test_join_text_spacing()
    test_merge_offsets_shift_timestamps()
    print("self-check ok")
