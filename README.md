# video-viewer

> ⚠️ **This is an early demo.** It works, but it's rough and has known problems (see
> [Known issues](#known-issues)). Expect bugs, and feel free to open an issue or suggest fixes.

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
python scripts/extract.py VIDEO --clean            # delete the extracted frames
```

Options: `--max-frames 150`, `--width 768`, `--model base|small|medium`, `--no-audio`, `--out DIR`.

Claude deletes the frames automatically once it has finished analyzing the video. The text files
(`timeline.md`, `transcript.txt`, `manifest.json`) are kept so it can still answer follow-up questions.

Output folder (default: `<temp>/video-viewer/<video name>/`):

| file | contents |
|---|---|
| `timeline.md` | one row per frame: time, change %, area %, label, speech |
| `transcript.txt` | timestamped speech |
| `manifest.json` | the same data, machine-readable |
| `frames/` | the extracted JPGs (deleted after analysis) |

## Known issues

This is a demo, so there are plenty of rough edges:

- **Only lightly tested:** tried on Windows with a couple of short videos. It hasn't been tested on macOS/Linux
  or with long, real-world footage.
- **Fast moments get missed:** anything faster than the gap between frames (0.5 s at 2/sec) can fall between two
  images. Claude can re-extract a short section at a higher rate, but only if it notices.
- **Long videos get thin:** output is capped at 150 frames, so a 10-minute video is sampled only about once every
  4 seconds.
- **The change score is crude:** it's just pixel differences. Camera shake, fades and lighting changes can look
  like big events, and some small but important changes can still score low.
- **Approximate timestamps:** frame times are calculated from the frame rate, not read from the video, so they
  can drift slightly.
- **Speech-to-text is basic:** it uses the small `base` Whisper model on the CPU. It can be slow on long videos,
  makes mistakes with accents, noise and music, and ignores videos with no speech (such as subtitle-only clips;
  Claude has to read on-screen text from the frames instead).
- **Uses lots of context:** Claude looks at many images, which uses up a lot of the conversation's tokens on
  longer videos.
- **Local files only:** you need a file path on your computer, so URLs (YouTube etc.) aren't supported.

## License

MIT
