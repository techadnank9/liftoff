"""Write the demo narration, one file per scene, into public/demo/vo/.

    python make_vo.py              # macOS voice (Samantha), free and local
    ELEVENLABS_API_KEY=... python make_vo.py   # ElevenLabs, if a key is set
"""
import json, os, subprocess, urllib.request
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "public/demo/vo"
OUT.mkdir(parents=True, exist_ok=True)
lines = json.loads((HERE / "vo_script.json").read_text())
key = os.environ.get("ELEVENLABS_API_KEY")
voice = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel

for i, text in enumerate(lines):
    wav = OUT / f"vo{i}.wav"
    if key:
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
            data=json.dumps({"text": text, "model_id": "eleven_multilingual_v2",
                             "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}).encode(),
            headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
        src = OUT / f"vo{i}.mp3"
        src.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    else:
        src = Path(f"/tmp/vo{i}.aiff")
        subprocess.run(["say", "-v", "Samantha (English (US))", "-r", "178", "-o", str(src), text], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-ar", "44100", "-ac", "2", str(wav)], check=True)
    if src.suffix == ".mp3":
        src.unlink()
    d = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)]))
    print(i, round(d, 2), "s")
