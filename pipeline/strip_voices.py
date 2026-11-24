#!/usr/bin/env python3
"""Stimmen (Voice-Chat, Kommentar, Mikro) aus Rohclips entfernen – nur Spielsound bleibt.

  python3 pipeline/strip_voices.py            # alle Clips in raw/, die in index/clips.json noch nicht "voices_removed" haben
  python3 pipeline/strip_voices.py raw/x.mp4  # einzelne Dateien

Trennt die Tonspur mit Demucs (htdemucs, --two-stems vocals) und ersetzt sie durch den "no_vocals"-Anteil.
Das Bild wird nicht neu kodiert. Markiert den Clip in index/clips.json mit "voices_removed": true
und speichert den Pegel der entfernten Stimmen ("voice_db") zur Kontrolle.
"""
import json, os, subprocess, sys, tempfile, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, "index", "clips.json")


def mean_db(wav):
    out = subprocess.run(["ffmpeg", "-i", wav, "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    for line in out.splitlines():
        if "mean_volume" in line:
            return float(line.split(":")[1].split("dB")[0])
    return None


def strip(path):
    tmp = tempfile.mkdtemp()
    try:
        wav = os.path.join(tmp, "a.wav")
        subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", path, "-vn", "-ac", "2", "-ar", "44100", wav])
        subprocess.check_call([sys.executable, "-m", "demucs", "--two-stems", "vocals", "-n", "htdemucs",
                               "-o", tmp, wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        sep = os.path.join(tmp, "htdemucs", "a")
        vdb = mean_db(os.path.join(sep, "vocals.wav"))
        out = path + ".nv.mp4"
        subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", path, "-i", os.path.join(sep, "no_vocals.wav"),
                               "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                               "-shortest", "-movflags", "+faststart", out])
        os.replace(out, path)
        return vdb
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    idx = json.load(open(IDX)) if os.path.exists(IDX) else {}
    files = sys.argv[1:] or [os.path.join("raw", k) for k, v in sorted(idx.items()) if not v.get("voices_removed")]
    for f in files:
        p = f if os.path.isabs(f) else os.path.join(ROOT, f)
        if not os.path.exists(p):
            continue
        vdb = strip(p)
        key = os.path.basename(p)
        e = idx.setdefault(key, {})
        e["voices_removed"] = True
        e["voice_db"] = vdb
        json.dump(idx, open(IDX, "w"), indent=1, ensure_ascii=False)
        print(f"{key}: Stimmen entfernt (Pegel der entfernten Stimmen {vdb} dB)", flush=True)
