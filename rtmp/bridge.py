import json
import os
import subprocess
import tempfile
import time
import urllib.request
import urllib.error
from pathlib import Path

SRS_API = os.getenv("SRS_API", "http://127.0.0.1:1985")
RTMP_BASE = os.getenv("RTMP_BASE", "rtmp://127.0.0.1:1935")
OCR_URL = os.getenv("OCR_URL", "https://roulette-production-f725c869.up.railway.app/api/screenshot")
API_SECRET = os.getenv("API_SECRET", "").strip()
POLL_SECONDS = float(os.getenv("BRIDGE_POLL_SECONDS", "2"))
FRAME_SECONDS = float(os.getenv("BRIDGE_FRAME_SECONDS", "2"))

def get_active_stream():
    try:
        with urllib.request.urlopen(SRS_API + "/api/v1/streams/", timeout=3) as r:
            data = json.loads(r.read().decode("utf-8"))
        for item in data.get("streams", []):
            publish = item.get("publish") or {}
            if publish.get("active"):
                app = item.get("app", "live")
                name = item.get("name", "")
                if app and name:
                    return f"{RTMP_BASE}/{app}/{name}"
    except Exception as exc:
        print(f"[bridge] SRS stream lookup: {exc}", flush=True)
    return None

def post_frame(path):
    if not API_SECRET:
        print("[bridge] API_SECRET missing; frame not sent", flush=True)
        return
    boundary = "----777UAFrameBoundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="frame.jpg"\r\n'
        "Content-Type: image/jpeg\r\n\r\n"
    ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        OCR_URL, data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                 "X-API-Secret": API_SECRET})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
            print("[bridge] OCR frame processed; candidates=" +
                  str(result.get("candidate_numbers", [])), flush=True)
    except urllib.error.HTTPError as exc:
        print(f"[bridge] OCR HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}", flush=True)
    except Exception as exc:
        print(f"[bridge] OCR request failed: {exc}", flush=True)

def main():
    print("[bridge] Frame bridge started; OCR results are NOT stored automatically.", flush=True)
    while True:
        stream_url = get_active_stream()
        if not stream_url:
            time.sleep(POLL_SECONDS)
            continue
        print("[bridge] Active stream found; starting frame extraction.", flush=True)
        with tempfile.TemporaryDirectory(prefix="777ua-") as folder:
            pattern = str(Path(folder) / "frame-%08d.jpg")
            command = [
                "ffmpeg", "-hide_banner", "-loglevel", "warning",
                "-i", stream_url, "-vf", f"fps=1/{FRAME_SECONDS}",
                "-q:v", "5", "-f", "image2", pattern
            ]
            process = subprocess.Popen(command, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.STDOUT)
            sent = set()
            try:
                while process.poll() is None:
                    for frame in sorted(Path(folder).glob("frame-*.jpg")):
                        if frame.name not in sent:
                            post_frame(frame)
                            sent.add(frame.name)
                            try:
                                frame.unlink()
                            except OSError:
                                pass
                    time.sleep(0.5)
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                print("[bridge] Stream ended; waiting for next publisher.", flush=True)
        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    main()
