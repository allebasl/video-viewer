"""Break a video into frames + transcript + a change-annotated timeline.

Usage:
  python extract.py VIDEO --probe                 # just print duration / frame estimate
  python extract.py VIDEO [--fps 2] [--out DIR] [--max-frames 150]
                          [--width 768] [--model base] [--no-audio]

Outputs (in --out, default: <tmp>/video-viewer/<video-stem>/):
  frames/frame_00001.jpg ...   sampled frames
  transcript.txt               timestamped speech (if any)
  timeline.md                  per-frame timestamp, visual change score, labels, speech
  manifest.json                same data, machine-readable
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
warnings.filterwarnings("ignore")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def need(mod, pip_name):
    try:
        return __import__(mod)
    except ImportError:
        sys.exit(f"Missing dependency '{pip_name}'. Install with:\n  python -m pip install {pip_name}")


imageio_ffmpeg = need("imageio_ffmpeg", "imageio-ffmpeg")
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def fmt(t):
    m, s = divmod(max(t, 0.0), 60)
    return f"{int(m):02d}:{s:04.1f}"


def probe(video):
    """Return (duration_seconds, has_audio, resolution) by parsing ffmpeg's banner."""
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", str(video)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    err = r.stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
    if not m:
        sys.exit(f"Could not read video '{video}'. ffmpeg said:\n{err[-800:]}")
    dur = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    res = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", err)
    return dur, ("Audio:" in err), (f"{res[1]}x{res[2]}" if res else "unknown")


def extract_frames(video, out, fps, width):
    fdir = out / "frames"
    fdir.mkdir(parents=True, exist_ok=True)
    for old in fdir.glob("frame_*.jpg"):
        old.unlink()
    vf = f"fps={fps},scale='min({width},iw)':-2"
    r = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-i", str(video),
                        "-vf", vf, "-q:v", "3", str(fdir / "frame_%05d.jpg")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.exit(f"Frame extraction failed:\n{r.stderr}")
    return sorted(fdir.glob("frame_*.jpg"))


def change_scores(frames):
    """For each frame vs the previous one: (overall change %, changed area %).

    overall = mean pixel difference on a tiny thumbnail (cuts, camera moves, big motion).
    area    = % of pixels that changed noticeably at higher resolution (catches small but
              meaningful changes such as on-screen text, a cursor, a number updating).
    """
    import numpy as np
    from PIL import Image
    scores, prev = [], None
    for f in frames:
        img = Image.open(f).convert("L")
        small = np.asarray(img.resize((96, 54)), dtype=np.float32)
        big = np.asarray(img.resize((320, 180)), dtype=np.float32)
        if prev is None:
            scores.append((None, None))
        else:
            overall = float(np.abs(small - prev[0]).mean() / 255 * 100)
            area = float((np.abs(big - prev[1]) > 30).mean() * 100)
            scores.append((overall, area))
        prev = (small, big)
    return scores


def label(score, area, cut):
    if score is None:
        return "START"
    if score >= cut:
        return "BIG CHANGE"
    if score >= 3 or area >= 3:
        return "change"
    if score >= 1 or area >= 0.2:
        return "minor"
    return "static"


def transcribe(video, out, model_name):
    wav = out / "audio.wav"
    r = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
                        "-vn", "-ac", "1", "-ar", "16000", str(wav)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not wav.exists():
        return None, "audio extraction failed"
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None, "faster-whisper not installed (python -m pip install faster-whisper)"
    print(f"Transcribing audio with faster-whisper '{model_name}' (first run downloads the model)...",
          flush=True)
    import wave
    import numpy as np
    with wave.open(str(wav), "rb") as w:  # decode ourselves; avoids PyAV version issues
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segs, info = model.transcribe(audio, vad_filter=True)
    segments = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segs]
    wav.unlink(missing_ok=True)
    return segments, f"language={info.language} (p={info.language_probability:.2f})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--fps", type=float, default=2.0)
    ap.add_argument("--out")
    ap.add_argument("--max-frames", type=int, default=150)
    ap.add_argument("--width", type=int, default=768)
    ap.add_argument("--model", default="base")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--probe", action="store_true")
    a = ap.parse_args()

    video = Path(a.video).expanduser().resolve()
    if not video.exists():
        sys.exit(f"Video not found: {video}")
    dur, has_audio, res = probe(video)

    if a.probe:
        print(f"duration_seconds: {dur:.1f}\nresolution: {res}\nhas_audio: {has_audio}")
        for f in (0.5, 1, 2, 4, 5):
            print(f"  at {f:g} fps -> ~{int(dur * f) + 1} frames")
        return

    fps = a.fps
    if dur * fps > a.max_frames:
        new = a.max_frames / dur
        print(f"NOTE: {fps:g} fps would give ~{int(dur * fps)} frames; capped to {new:.3f} fps "
              f"(--max-frames {a.max_frames}). Raise --max-frames to override.")
        fps = new

    out = Path(a.out) if a.out else Path(tempfile.gettempdir()) / "video-viewer" / video.stem
    out.mkdir(parents=True, exist_ok=True)

    frames = extract_frames(video, out, fps, a.width)
    scores = change_scores(frames)
    real = [s for s, _ in scores if s is not None]
    # "Big change" = clearly above this video's typical motion, and at least 12%.
    cut = max(12.0, (sorted(real)[int(len(real) * 0.9)] if len(real) >= 10 else 0))

    segments, audio_note = (None, "skipped (--no-audio)")
    if not a.no_audio:
        segments, audio_note = transcribe(video, out, a.model) if has_audio else (None, "video has no audio track")

    step = 1 / fps
    rows = []
    for i, (f, (s, area)) in enumerate(zip(frames, scores)):
        t0 = i * step
        speech = [g["text"] for g in (segments or []) if g["start"] < t0 + step and g["end"] > t0]
        rows.append({"frame": f.name, "path": str(f), "time": round(t0, 2), "change_pct": None if s is None else round(s, 2),
                     "area_pct": None if area is None else round(area, 2), "label": label(s, area, cut), "speech": " ".join(speech)})

    if segments is not None:
        (out / "transcript.txt").write_text(
            "\n".join(f"[{fmt(g['start'])} - {fmt(g['end'])}] {g['text']}" for g in segments) or "(no speech detected)",
            encoding="utf-8")

    big = [r for r in rows if r["label"] in ("START", "BIG CHANGE")]
    lines = [f"# Video timeline: {video.name}", "",
             f"- duration: {fmt(dur)} ({dur:.1f}s), resolution {res}",
             f"- sampled at {fps:.3g} fps -> {len(frames)} frames (one every {step:.2f}s), folder: {out / 'frames'}",
             f"- big-change threshold: {cut:.1f}% pixel difference; {len(big) - 1} big changes found",
             f"- audio: {audio_note}" + (f", {len(segments)} speech segments" if segments else ""),
             "", "Legend (each vs the previous frame): change % = overall difference; area % = share of the image "
             "that changed noticeably. static = nothing moved; minor = small local change (text, cursor, small "
             "motion); change = clear motion; BIG CHANGE = likely cut / new scene / major movement.", "",
             "| frame | time | change % | area % | label | speech during this frame |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        c = "-" if r["change_pct"] is None else f"{r['change_pct']:.1f}"
        ar = "-" if r["area_pct"] is None else f"{r['area_pct']:.1f}"
        lines.append(f"| {r['frame']} | {fmt(r['time'])} | {c} | {ar} | {r['label']} | {r['speech'].replace('|', '/')} |")
    (out / "timeline.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps({
        "video": str(video), "duration": dur, "resolution": res, "fps": fps, "big_change_threshold": cut,
        "audio": audio_note, "transcript": segments, "frames": rows}, indent=1), encoding="utf-8")

    print(f"Done. {len(frames)} frames, {len(big) - 1} big changes, audio: {audio_note}")
    print(f"Output folder: {out}")
    print(f"Read first: {out / 'timeline.md'}")
    if segments is not None:
        print(f"Transcript:  {out / 'transcript.txt'}")


if __name__ == "__main__":
    main()
