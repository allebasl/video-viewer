---
name: video-viewer
description: Lets Claude actually watch a video. It breaks the video into frames (2 per second by default, after asking the user), transcribes the audio with faster-whisper, and analyzes what CHANGES from frame to frame so Claude understands motion, events and timing, not just still images. Use this whenever the user sends, attaches, drops or points to a video file (.mp4, .mov, .webm, .mkv, .avi, .m4v, screen recordings, clips), or asks Claude to watch, view, summarize, describe, transcribe or answer questions about a video, even if they don't say "frames" or name this skill.
---

# Video Viewer

Claude can't play video, but it can look at images and read text. This skill turns a video into
**a timed sequence of frames + a transcript + a change score for each frame**, so you can understand it
*as a video*: what happens, in what order, what moves, appears or disappears, and what is said while it happens.

The main idea: **a video is the changes between frames.** A single frame shows a scene. The difference
between frame N and frame N+1 shows the action. Look at the frames in order and keep asking what
changed since the last one.

## Workflow

### 1. Find the video and probe it
Get the path to the video file (from the user's message, an attachment path, or by asking). Then run:

```bash
python ~/.claude/skills/video-viewer/scripts/extract.py "<video>" --probe
```

This prints the duration, the resolution, whether there's audio, and the frame count at several rates.

### 2. Ask the user for the frame rate (default 2 per second)
Ask before extracting, and show the numbers so the user can choose, e.g.:

> This video is 0:45 long and has audio. How many images per second should I take?
> Default is **2/sec (≈91 images)**. Use 1/sec (≈46) for a quicker look, or 4–5/sec for fast action.

If the user already gave a rate in their message ("use 5 fps"), or says "default"/"just do it",
don't ask again; use what they said (2 if nothing). Higher rates catch fast motion but cost more
images to view. The script caps output at 150 frames by default and says so if it lowers the rate.
Pass `--max-frames N` if the user really wants more.

### 3. Extract
```bash
python ~/.claude/skills/video-viewer/scripts/extract.py "<video>" --fps <rate>
```
Useful flags: `--no-audio` (skip transcription), `--model small` (more accurate speech, slower; the default is `base`),
`--out <dir>`. The first transcription downloads a speech model (~150MB), so tell the user if it takes a while.
If a dependency is missing, the script prints the `pip install` command to run.

The script prints the output folder. It contains:
- `timeline.md`: **read this first.** It has one row per frame with the timestamp, **change %** (overall difference
  from the previous frame, which flags cuts and big motion), **area %** (how much of the image changed, which catches small
  changes like on-screen text, a cursor or a counter), a label (START / static / minor / change / BIG CHANGE) and the speech
  during that frame.
- `transcript.txt`: the full timestamped speech.
- `frames/frame_00001.jpg …`: the images.

### 4. Watch the video
1. Read `timeline.md` and `transcript.txt` to get the shape of the video: where the cuts and busy stretches are,
   where it's static, and what's said when.
2. View the frames **in chronological order** with the Read tool. Read several images per message
   (batches of about 10–20 in parallel) so you see neighboring frames together.
   - With ~60 frames or fewer, look at all of them.
   - With more, look at every frame labeled BIG CHANGE or change, the frame just **before** each one (so you
     can see the before/after), and a sample of the static/minor runs (about one per 2–3 seconds). Long static
     stretches really are the same picture, and the change score already tells you so.
3. For each step, note **what changed**: objects or people entering/leaving, movement direction, camera moves
   (pan/zoom/cut), text or UI appearing on screen, expressions and gestures, and on-screen text changing.
   Link the changes to the speech at the same timestamp, since what's said often explains what's shown.
4. Treat the change % as a hint, not the truth. Camera shake gives high scores with no real event, and a small
   but important change (a cursor click, a number updating) can score low. Your eyes decide.

### 5. Report
Unless the user asked a specific question (then answer it directly, citing timestamps as evidence), give:

```
## Summary
2–4 sentences: what the video is and what happens.

## Timeline
- 00:00 – 00:04  Opening: ... (the scene)
- 00:04  CUT → ... (what changed)
- 00:07 – 00:15  ... moves/does ...; speaker says "..."
...

## Audio / Speech
Short summary of what's said (or "no speech" / "music only"). Quote key lines with timestamps.

## Notable details
Anything easy to miss: on-screen text, small changes, things that contradict the audio, etc.
```

Write it as a description of motion and events over time ("the person picks up the cup at 0:06 and walks
out of frame by 0:09"), not as a list of separate still images. That's what makes it watching a video
rather than looking at a slideshow.

Be honest about the limits of sampling: anything faster than the frame interval (0.5s at 2/sec) may be
missed. If something important seems to happen between two frames, say so, and offer to re-extract that
section at a higher rate.

### Follow-ups
The frames stay in the output folder, so you can answer follow-up questions by re-reading specific frames
instead of extracting again. To zoom in on a short section at a higher rate, cut it with the bundled ffmpeg:

```bash
python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"
"<ffmpeg>" -ss 00:00:12 -to 00:00:16 -i "<video>" -c copy clip.mp4
```
Then run extract.py on `clip.mp4` with a higher `--fps` and a separate `--out`.
