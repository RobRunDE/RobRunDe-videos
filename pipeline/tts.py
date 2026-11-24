"""German AI voice-over with Piper (free, offline).

Usage (library):  from tts import make_voiceover
    beats = ["Satz eins.", "Satz zwei ..."]
    info = make_voiceover(beats, "work/vo.wav")
    -> {"duration": s, "beats": [{"start","end"}], "words": [[start,end,word], ...]}

English gaming terms are respelled so the German voice says them naturally.
Add new terms to EN below whenever a word sounds wrong.
"""
import json, os, re, subprocess, sys, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "config.json")))
VOICE_DIR = os.path.join(HERE, "voices")

EN = {
    "ROB RUN": "Robb Rann", "Rob Run": "Robb Rann", "RobRun": "Robb Rann",
    "Keycards": "Kiekards", "Keycard": "Kiekard", "Loot": "Luut", "looten": "luuten", "Looten": "Luuten",
    "gelootet": "geluutet", "Raid": "Räid", "Raids": "Räids", "raiden": "räiden", "Gameplay": "Gäimplei",
    "Game": "Gäim", "Games": "Gäims", "Hideout": "Haidaut", "Extraction": "Exträkschen", "Extract": "Exträkt",
    "Spawn": "Spoon", "spawnen": "spoonen", "Clan": "Klän", "Clans": "Kläns", "Steam": "Stiem",
    "Upgrade": "Apgräid", "Upgrades": "Apgräids", "Level": "Läwwel", "Easy": "Iesie", "easy": "iesie",
    "Noob": "Nuub", "Noobs": "Nuubs", "Cash": "Käsch", "Safe": "Säif", "Skill": "Skill", "Skills": "Skills",
    "Tipp": "Tipp", "Pro": "Proh", "Pro-Tipp": "Proh-Tipp", "Fail": "Fäil", "Fails": "Fäils",
    "Highlight": "Hailait", "Highlights": "Hailaits", "Team": "Tiem", "Squad": "Skwodd", "Solo": "Solo",
    "Heist": "Haist", "Cops": "Kopps", "Cop": "Kopp", "Fake": "Fäik", "Insane": "Inssäin", "Lowkey": "Lohkie",
    "Gear": "Gier", "Drop": "Dropp", "droppen": "droppen", "Map": "Mäpp", "Spot": "Spott", "Boss": "Boss",
    "Speedrun": "Spiedrann", "Glitch": "Glitsch", "Bug": "Bagg", "Update": "Apdäit", "Patch": "Pätsch",
    "Early Access": "Örli Äkzess", "Battle": "Bättel", "Loadout": "Loudaut", "Headshot": "Hedschott",
    "Grind": "Graind", "grinden": "grainden", "Fun Fact": "Fann Fäkt", "Content": "Kontent", "Follow": "Follo",
}

def prep(t):
    for k in sorted(EN, key=len, reverse=True):
        t = re.sub(r'(?<!\w)' + re.escape(k) + r'(?!\w)', EN[k], t)
    return t

_voice = None
def voice():
    global _voice
    if _voice is None:
        from piper import PiperVoice
        _voice = PiperVoice.load(os.path.join(VOICE_DIR, CFG["voice"] + ".onnx"))
    return _voice

def _speech_bounds(a, sr):
    env = np.abs(a)
    thr = max(0.02, env.max() * 0.06)
    idx = np.where(env > thr)[0]
    if len(idx) == 0: return 0, len(a)
    return idx[0], idx[-1]

def _syl(w):
    return max(1, len(re.findall(r'[aeiouäöüy]+', w.lower()))) + 0.15 * len(w)

def make_voiceover(beats, out_wav, gap=0.14, pauses=None):
    from piper import SynthesisConfig
    v = voice()
    cfg = SynthesisConfig(length_scale=CFG["length_scale"], noise_scale=CFG["noise_scale"], noise_w_scale=CFG["noise_w_scale"])
    sr = v.config.sample_rate
    pieces, words, binfo, t = [], [], [], 0.0
    for bi, text in enumerate(beats):
        b0 = t
        # synthesize sentence by sentence so each word can be timed within its sentence
        sents = [s for s in re.split(r'(?<=[.!?…])\s+', text.strip()) if s]
        for s in sents:
            audio = np.concatenate([c.audio_float_array for c in v.synthesize(prep(s), syn_config=cfg)])
            i0, i1 = _speech_bounds(audio, sr)
            audio = audio[max(0, i0 - int(0.03 * sr)): i1 + int(0.08 * sr)]
            dur = len(audio) / sr
            ws = s.split()
            wts = np.array([_syl(w) for w in ws]); wts = wts / wts.sum()
            span = dur - 0.11
            c = t + 0.03
            for w, f in zip(ws, wts):
                words.append([round(c, 3), round(c + f * span, 3), w]); c += f * span
            pieces.append(audio); t += dur
            pieces.append(np.zeros(int(gap * sr), np.float32)); t += gap
        extra = (pauses or [0] * len(beats))[bi] or 0
        if extra > 0:
            pieces.append(np.zeros(int(extra * sr), np.float32)); t += extra
        binfo.append({"start": round(b0, 3), "end": round(t, 3)})
    full = np.concatenate(pieces)
    raw = out_wav.replace(".wav", "_raw.wav")
    with wave.open(raw, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(full, -1, 1) * 32767).astype(np.int16).tobytes())
    p = CFG["pitch"]
    af = (f"aresample=48000,asetrate=48000*{p},aresample=48000,atempo={1/p:.5f},highpass=f=80,"
          "equalizer=f=220:t=q:w=1:g=-2,equalizer=f=3500:t=q:w=1.2:g=3,"
          "acompressor=threshold=-20dB:ratio=3:attack=5:release=80,loudnorm=I=-16:TP=-2")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-af", af, "-ac", "1", out_wav], check=True)
    info = {"duration": round(t, 3), "beats": binfo, "words": words}
    json.dump(info, open(out_wav.replace(".wav", ".json"), "w"), ensure_ascii=False, indent=1)
    return info

if __name__ == "__main__":
    # quick test: python3 tts.py "Text" out.wav
    print(make_voiceover([sys.argv[1]], sys.argv[2]))
