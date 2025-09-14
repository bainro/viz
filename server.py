import os
import csv
import cv2
import json
import time
import uuid
import queue
import threading
import subprocess
import webbrowser 
import numpy as np
from pathlib import Path
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS

# -----------------------
# Config
# -----------------------
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "recorded_sessions"
RESULT_DIR = BASE_DIR / "detection_results"
DB_PATH = BASE_DIR / "jobs.json"

UPLOAD_DIR.mkdir(exist_ok=True)
RESULT_DIR.mkdir(exist_ok=True)

MAX_CONTENT_LENGTH = 200 * 1024 * 1024 * 1024  # 200 GB (adjust as needed)
ALLOWED_EXTENSIONS = {'.webm', '.mp4', '.mkv', '.mov', '.avi', '.ogg'}

# Fake "DLC" generation
DEFAULT_FPS = 30

# -----------------------
# App & CORS
# -----------------------
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
# Allow local dev from any port (you can restrict this later)
CORS(app, resources={r"/*": {"origins": "*"}})

# -----------------------
# In-memory "DB" + worker queue
# -----------------------
jobs_lock = threading.Lock()
jobs = {}  # job_id -> dict
work_q = queue.Queue()

def load_db():
    if DB_PATH.exists():
        try:
            data = json.loads(DB_PATH.read_text())
            with jobs_lock:
                jobs.update(data)
        except Exception:
            pass

def save_db():
    with jobs_lock:
        DB_PATH.write_text(json.dumps(jobs, indent=2))

load_db()

# -----------------------
# Helpers
# -----------------------
def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS

def new_job_id() -> str:
    return uuid.uuid4().hex

def mark_job(job_id: str, **patch):
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(patch)
    save_db()

def get_job(job_id: str):
    with jobs_lock:
        return jobs.get(job_id)

# -----------------------
# Fake "DLC result" generator
# -----------------------
def generate_fake_result_json(job):
    """
    Create a small, DLC-like JSON file:
      {
        "fps": 30,
        "width": ...,
        "height": ...,
        "point_types": ["nose", "tailbase", ...],
        "frames": [
          {"points": {"nose":[x,y,lik], "tailbase":[x,y,lik] ...}},
          ...
        ]
      }
    Uses job['duration'] to set number of frames (fps * duration).
    """
    width = int(job.get('width') or 1280)
    height = int(job.get('height') or 720)
    fps = int(job.get('fps') or DEFAULT_FPS)
    duration = int(job.get('duration') or 5)
    n_frames = max(1, min(fps * duration, 9000))  # cap to keep file reasonable

    # A small set of points typical for center-of-mass averaging
    point_types = ["nose", "earsLeft", "earsRight", "tailBase"]

    frames = []
    # simple wandering with light jitter
    cx, cy = width * 0.5, height * 0.5
    vx, vy = width * 0.002, height * 0.0015

    import random
    for i in range(n_frames):
        # drift
        cx += vx + random.uniform(-1.5, 1.5)
        cy += vy + random.uniform(-1.5, 1.5)
        cx = max(0, min(width - 1, cx))
        cy = max(0, min(height - 1, cy))

        # scatter points around center
        pts = {}
        for name in point_types:
            ox = random.uniform(-12, 12)
            oy = random.uniform(-12, 12)
            lik = max(0.0, min(1.0, random.gauss(0.85, 0.08)))
            pts[name] = [round(cx + ox, 3), round(cy + oy, 3), round(lik, 3)]
        frames.append({"points": pts})

    payload = {
        "fps": fps,
        "width": width,
        "height": height,
        "point_types": point_types,
        "frames": frames
    }
    return payload

def worker():
    while True:
        job_id = work_q.get()
        if job_id is None:
            break
        job = get_job(job_id)
        if not job:
            continue
        try:
            sleep_s = min(10, max(2, int(job.get('duration') or 5) // 2))
            time.sleep(sleep_s)

            #mark_job(job_id, status="processing", started_at=datetime.utcnow().isoformat())

            # Simulate processing time (replace with real DLC call later)
            # For realism, scale a bit with video length (but cap)
            #sleep_s = min(10, max(2, int(job.get('duration') or 5) // 2))
            #time.sleep(sleep_s)

            # Build fake DLC-like result JSON and save to disk
            #result_payload = generate_fake_result_json(job)
            #result_path = RESULT_DIR / f"{job_id}.json"
            #with result_path.open("w", encoding="utf-8") as f:
            #    json.dump(result_payload, f)

            #mark_job(job_id, status="ready", result_path=str(result_path))
        except Exception as e:
            #mark_job(job_id, status="error", error=str(e))
            continue
        #finally:
        #    work_q.task_done()

worker_thread = threading.Thread(target=worker, daemon=True)
worker_thread.start()

def is_ffmpeg_available():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except Exception:
        return False

def has_ffmpeg():
    return is_ffmpeg_available()

import subprocess
import json
import shlex

def run_ffmpeg_cut(src_path: str, start: float, end: float, out_path: str):
    """
    Hybrid cut:
      - If input is H.264 + AAC in MP4/MOV/MKV → fast stream copy
      - Otherwise → re-encode w/ accurate seeking (fast seek + precise seek)
    """
    duration = max(0.0, end - start)
    if duration <= 0:
        raise ValueError("Non-positive segment duration.")

    # --- Probe codecs ---
    probe_cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name", "-of", "json", src_path
    ]
    probe_out = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    video_codec = None
    if probe_out.returncode == 0:
        info = json.loads(probe_out.stdout)
        if info.get("streams"):
            video_codec = info["streams"][0].get("codec_name")

    probe_cmd = [
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_name", "-of", "json", src_path
    ]
    probe_out = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    audio_codec = None
    if probe_out.returncode == 0:
        info = json.loads(probe_out.stdout)
        if info.get("streams"):
            audio_codec = info["streams"][0].get("codec_name")

    # --- Decide mode ---
    #safe_copy = (video_codec == "h264" and (audio_codec in ("aac", None)))

    fast_seek = max(0, start - 2.0)
    precise_seek = start - fast_seek

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{fast_seek:.3f}",   # coarse seek
        "-i", src_path,
        "-ss", f"{precise_seek:.3f}",  # fine seek
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast",
        "-c:a", "aac",
        "-movflags", "+faststart",
        out_path,
    ]

    # --- Run command ---
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}):\n{proc.stderr[:1000]}")

    return out_path

# Keep track of recording sessions
sessions = {}

# -----------------------
# Routes
# -----------------------

@app.route("/upload-video", methods=["POST"])
def upload_video():
    if "video" not in request.files:
        return jsonify(error="No 'video' file in form-data"), 400
    f = request.files["video"]
    if not f.filename:
        return jsonify(error="Empty filename"), 400
    session_id = str(uuid.uuid4())
    sess_dir = UPLOAD_DIR / session_id
    sess_dir.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(f.filename)[1] or ".mp4"
    save_path = sess_dir / f"source{ext}"
    f.save(str(save_path))
    return jsonify(video_path=str(save_path))

@app.route("/cut-video", methods=["POST"])
def cut_video():
    data = request.get_json(silent=True) or {}
    src = data.get("video_path")
    base_name = data.get("base_name") or ""
    precise = bool(data.get("precise", False))
    segs = data.get("segments") or []

    if not src or not os.path.isfile(src):
        return jsonify(error="Invalid or missing 'video_path'."), 400

    # 🟢 Place split_videos/ in the same parent as the source
    parent_dir = Path(src).parent
    out_dir_path = parent_dir / "split_videos" / base_name[-4:] # files w/ more than 10 cams
    out_dir_path.mkdir(parents=True, exist_ok=True)

    outputs = []
    for i, seg in enumerate(segs, start=1):
        start = float(seg["start"])
        end = float(seg["end"])
        if end <= start:
            return jsonify(error=f"Segment {i} has non-positive duration"), 400

        out_name = f"{base_name}_clip_{i:02d}.mp4"
        out_path = out_dir_path / out_name
        run_ffmpeg_cut(src_path=src, start=start, end=end,
                       out_path=str(out_path))
        outputs.append(str(out_path))

    return jsonify(status="ok", out_dir=str(out_dir_path), outputs=outputs)


@app.route("/export-roi-videos", methods=["POST"])
def export_roi_videos():
    data = request.get_json(silent=True) or {}
    src = data.get("video_path")
    rois = data.get("rois") or []
    margin = int(data.get("margin", 0))
    base_name = data.get("base_name") or Path(src).stem

    if not src or not os.path.isfile(src):
        return jsonify(error="Invalid 'video_path'"), 400
    if not rois:
        return jsonify(error="No ROIs provided"), 400

    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        return jsonify(error="Could not open video"), 400

    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps    = cap.get(cv2.CAP_PROP_FPS) or 30.0

    parent_dir = Path(src).parent
    out_dir_path = parent_dir / "roi_videos"
    out_dir_path.mkdir(parents=True, exist_ok=True)

    writers, roi_meta = [], []
    for i, roi in enumerate(rois, start=1):
        # sanitize label for filenames
        label = (roi.get("label") or f"roi{i}").replace(" ", "_")
        pts = np.array(roi["points"], dtype=np.float32)

        # bounding box
        x0 = max(0, int(np.floor(pts[:,0].min())) - margin)
        y0 = max(0, int(np.floor(pts[:,1].min())) - margin)
        x1 = min(width-1, int(np.ceil(pts[:,0].max())) + margin)
        y1 = min(height-1, int(np.ceil(pts[:,1].max())) + margin)
        w, h = max(1, x1-x0+1), max(1, y1-y0+1)

        shifted = (pts - np.array([[x0, y0]], dtype=np.float32)).astype(np.int32).reshape((-1,1,2))
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(mask, [shifted], 255)

        # 👉 output file now includes label
        out_path = out_dir_path / f"{label}"
        out_path.mkdir(parents=True, exist_ok=True)
        out_path = out_path  / f"{base_name}.mp4"

        cmd = [
            "ffmpeg", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "bgr24",
            "-s", f"{w}x{h}", "-r", f"{fps:.03f}",
            "-i", "pipe:0",
            "-vf", "pad=width=ceil(iw/2)*2:height=ceil(ih/2)*2",
            "-an", "-c:v", "libx264", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", str(out_path)
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        writers.append((proc, w, h))
        roi_meta.append((label, x0, y0, x1, y1, shifted, mask))

    # write frames
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            for (proc, w, h), meta in zip(writers, roi_meta):
                _, x0, y0, x1, y1, _, mask = meta
                crop = frame[y0:y1+1, x0:x1+1].copy()
                crop[mask==0] = (0,0,0)
                proc.stdin.write(crop.tobytes())
    finally:
        cap.release()
        for proc, _, _ in writers:
            try: proc.stdin.close(); proc.wait()
            except: pass

    return jsonify(status="ok", out_dir=str(out_dir_path))



@app.route("/start-recording", methods=["POST"])
def start_recording():
    data = request.get_json(silent=True) or {}
    basename = data.get("basename", "").strip()

    # timestamp-based session name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_name = f"{timestamp}_{basename}" if basename else timestamp

    session_dir = UPLOAD_DIR / session_name
    session_dir.mkdir(parents=True, exist_ok=True)

    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "dir": str(session_dir),
        "session_name": session_name,
        "cams": {}
    }

    return jsonify({"session_id": session_id, "session_dir": str(session_dir)})

@app.route("/upload-chunk", methods=["POST"])
def upload_chunk():
    session_id = request.form.get("streamId")
    cam_id = request.form.get("camId")
    if session_id not in sessions:
        return jsonify({"error": "Invalid session"}), 400

    sess = sessions[session_id]
    session_name = sess["session_name"]
    session_dir = Path(sess["dir"])

    if cam_id not in sess["cams"]:
        # ✅ build filenames like 20250808_1212023_test_cam1.mp4
        out_file = session_dir / f"{session_name}_cam{cam_id}.mp4"
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-f", "webm", "-i", "pipe:0",
            "-c:v", "libx264", "-preset", "veryfast",
            str(out_file)
        ]
        proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
        sess["cams"][cam_id] = {"proc": proc, "file": str(out_file)}

    chunk = request.files["chunk"].read()
    proc = sess["cams"][cam_id]["proc"]
    proc.stdin.write(chunk)
    proc.stdin.flush()

    return jsonify({"status": f"chunk received for cam {cam_id}"})

@app.route("/detect-color", methods=["POST"])
def detect_color():
    """
    JSON:
    {
      "videos": ["/abs/path/roi1.mp4", "/abs/path/roi2.mp4"],  # or single "video_path"
      "params": {"v_low":0, "v_high":80, "min_frac":0.05}
    }
    Outputs per job: outputs/detect/<job_id>/<basename>_annotated.mp4 and <basename>_detections.csv
    CSV columns: timestamp_sec,roi_name
    ROI name defaults to video basename (no extension).
    """
    if not is_ffmpeg_available():
        return jsonify(error="ffmpeg not found on PATH"), 500

    data = request.get_json(silent=True) or {}
    videos = data.get("videos") or ([] if not data.get("video_path") else [data.get("video_path")])
    params = data.get("params") or {}
    v_low  = int(params.get("v_low", 0))
    v_high = int(params.get("v_high", 80))
    min_frac = float(params.get("min_frac", 0.05))

    if not videos:
        return jsonify(error="No videos provided"), 400

    job_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_dir = RESULT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    for k, vid in enumerate(videos):
        if not os.path.isfile(vid):
            return jsonify(error=f"Missing/video not found: {vid}"), 400

        cap = cv2.VideoCapture(vid)
        if not cap.isOpened():
            return jsonify(error=f"Could not open: {vid}"), 400

        width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps    = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        base   = Path(vid).stem + f"_{k}"
        roi_name = base
        out_mp4 = job_dir / f"{base}_annotated.mp4"
        out_csv = job_dir / f"{base}_detections.csv"

        # ffmpeg sink (pad to even size for libx264)
        cmd = [
            "ffmpeg", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "bgr24",
            "-s", f"{width}x{height}", "-r", f"{fps:.03f}",
            "-i", "pipe:0",
            "-vf", "pad=width=ceil(iw/2)*2:height=ceil(ih/2)*2",
            "-an",
            "-c:v", "libx264", "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            str(out_mp4)
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

        # CSV writer
        with open(out_csv, "w", newline="") as fcsv:
            w = csv.writer(fcsv)
            w.writerow(["timestamp_sec", "roi_name"])

            frame_idx = 0
            try:
                while True:
                    ok, frame = cap.read()
                    if not ok:
                        break

                    # HSV threshold (Value in [v_low, v_high])
                    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                    mask = cv2.inRange(hsv, (0, 0, v_low), (179, 255, v_high))
                    frac = float(cv2.countNonZero(mask)) / (frame.shape[0]*frame.shape[1])

                    # annotate if detection
                    if frac >= min_frac:
                        cv2.circle(frame, (12,12), 8, (0,0,255), -1)  # red dot top-left
                        ts = frame_idx / fps
                        w.writerow([f"{ts:.3f}", roi_name])

                    # write frame
                    proc.stdin.write(frame.tobytes())
                    frame_idx += 1
            finally:
                cap.release()
                try:
                    proc.stdin.close(); proc.wait()
                except Exception:
                    pass

    return jsonify(status="ok", job_id=job_id, out_dir=str(job_dir))

@app.route("/stop-recording", methods=["POST"])
def stop_recording():
    session_id = request.json.get("session_id")
    if session_id not in sessions:
        return jsonify({"error": "Invalid session"}), 400

    files = []
    for _cam_id, cam in sessions[session_id]["cams"].items():
        proc = cam["proc"]
        proc.stdin.close()
        proc.wait()
        files.append(cam["file"])

    del sessions[session_id]
    return jsonify({"status": "stopped", "outputs": files})

@app.route("/<path:filename>")
def static_files(filename):
    # Serve any other static file in the same folder (CSS, JS, etc.)
    return send_from_directory('.', filename)

@app.route("/upload", methods=["POST"])
def upload():
    """
    Expects multipart/form-data:
      - file: the video blob
      - name, duration, width, height (optional extra metadata)
    Returns: { job_id: "..." }
    """
    if 'file' not in request.files:
        return jsonify({"error": "missing file"}), 400

    f = request.files['file']
    if f.filename == '':
        return jsonify({"error": "empty filename"}), 400

    if not allowed_file(f.filename):
        return jsonify({"error": "unsupported file type"}), 400

    # Metadata from the front-end form
    name = request.form.get('name') or f.filename
    duration = int(request.form.get('duration') or 0)
    width = int(request.form.get('width') or 0)
    height = int(request.form.get('height') or 0)

    job_id = new_job_id()
    safe_name = secure_filename(name)
    # Unique file name
    save_name = f"{Path(safe_name).stem}_{job_id}{Path(safe_name).suffix}"
    save_path = UPLOAD_DIR / save_name
    f.save(save_path)

    job = {
        "job_id": job_id,
        "name": safe_name,
        "filename": save_name,
        "filepath": str(save_path),
        "status": "queued",
        "created_at": datetime.utcnow().isoformat(),
        "duration": duration,
        "width": width,
        "height": height,
        "fps": DEFAULT_FPS
    }
    with jobs_lock:
        jobs[job_id] = job
    save_db()

    # Enqueue for background "processing"
    work_q.put(job_id)

    return jsonify({"job_id": job_id})

@app.route("/jobs", methods=["GET"])
def list_jobs():
    with jobs_lock:
        # Keep payload small: only fields the front-end cares about
        out = [{"job_id": j["job_id"], "status": j["status"], "name": j.get("name", "")}
               for j in jobs.values()]
    return jsonify({"jobs": out})

@app.route("/result/<job_id>", methods=["GET"])
def get_result(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "unknown job_id"}), 404

    status = job.get("status")
    if status != "ready":
        # Client expects non-OK when not ready (your JS handles !res.ok)
        return jsonify({"status": status, "message": "Not ready"}), 409

    result_path = job.get("result_path")
    if not result_path or not Path(result_path).exists():
        return jsonify({"error": "result missing"}), 500

    with open(result_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)

# (Optional) serve uploaded files if you want to link them later
@app.route("/uploads/<path:fname>", methods=["GET"])
def serve_upload(fname):
    # @TODO try as_attachment=True
    return send_from_directory(UPLOAD_DIR, fname, as_attachment=False)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True})

# -----------------------
# Graceful shutdown hook (optional)
# -----------------------
def shutdown_worker():
    try:
        work_q.put_nowait(None)
    except Exception:
        pass

import atexit
atexit.register(shutdown_worker)

if __name__ == "__main__":
    url = "http://127.0.0.1:5000/record.html"
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        print(f'{os.environ.get("WERKZEUG_RUN_MAIN")=}')
        webbrowser.open(url)
    app.run(host="127.0.0.1", port=5000, debug=True) 