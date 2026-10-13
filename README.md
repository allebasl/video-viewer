# video-viewer

A [Claude Code](https://claude.com/claude-code) skill that lets Claude **watch videos**.

Claude can't play video, but it can look at images and read text. This skill turns a video into:

- **frames**: 2 per second by default (Claude asks you first and shows how many images each rate gives)
- **a transcript**: speech-to-text with timestamps, done locally and for free with [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- **a change timeline**: every frame is scored by how much it changed from the one before, so Claude can find
  cuts, motion and small changes such as on-screen text or a cursor

Claude then looks at the frames in order, asking *what changed?* each time, and describes the video as a
sequence of events with timestamps instead of a pile of separate pictures.

## Install

1. Copy this folder into your skills directory:

   ```bash
   git clone https://github.com/allebasl/video-viewer ~/.claude/skills/video-viewer
   ```

2. Install the Python dependencies (Python 3.9+):

   ```bash
   python -m pip install -r ~/.claude/skills/video-viewer/requirements.txt
   ```

   `imageio-ffmpeg` includes its own copy of ffmpeg, so you don't need to install ffmpeg separately.
   The first transcription downloads a speech model (~150 MB).

## Use

Paste a video path into Claude Code:

```
watch "C:\Users\me\Videos\clip.mp4" and tell me what happens
```

or run `/video-viewer <path> <question>`. Claude checks the video, asks how many frames per second to use
(reply `default` for 2/sec), extracts everything, and reports a summary, a timeline, what was said, and any
details that are easy to miss.

## The script on its own

```bash
python scripts/extract.py VIDEO --probe            # duration, audio, frame-count estimates
python scripts/extract.py VIDEO --fps 2            # frames + transcript + timeline.md
```

Options: `--max-frames 150`, `--width 768`, `--model base|small|medium`, `--no-audio`, `--out DIR`.

Output folder (default: `<temp>/video-viewer/<video name>/`):

| file | contents |
|---|---|
| `timeline.md` | one row per frame: time, change %, area %, label, speech |
| `transcript.txt` | timestamped speech |
| `manifest.json` | the same data, machine-readable |
| `frames/` | the extracted JPGs |

## Limits

- Anything faster than the gap between frames (0.5 s at 2/sec) can be missed. Claude says so and can re-extract a
  short section at a higher rate.
- Output is capped at 150 frames by default, so long videos get a lower frame rate automatically.

## License

MIT
