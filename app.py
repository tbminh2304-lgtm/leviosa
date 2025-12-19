from flask import Flask, render_template, request, send_from_directory
import os
import whisper
import uuid
import re
import subprocess

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Load Whisper model (Render Free nên dùng base)
model = whisper.load_model("base")


def format_time(seconds):
    """Chuyển đổi giây thành định dạng thời gian HH:MM:SS,SSS"""
    ms = int((seconds - int(seconds)) * 1000)
    s = int(seconds) % 60
    m = int(seconds) // 60 % 60
    h = int(seconds) // 3600
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def split_text_to_fake_segments(text):
    """Fallback: tách câu khi Whisper không trả segments"""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    segments = []
    t = 0.0
    for s in sentences:
        if s.strip():
            segments.append({
                "start": t,
                "end": t + 2.5,
                "text": s
            })
            t += 2.5
    return segments


@app.route("/", methods=["GET", "POST"])
def index():
    text = ""
    subtitles = []
    mode = "text"
    error = None
    video_path = None

    if request.method == "POST":
        mode = request.form.get("mode", "text")
        video = request.files["video"]

        # Lưu video
        video_filename = f"{uuid.uuid4()}_{video.filename}"
        video_path = os.path.join(UPLOAD_FOLDER, video_filename)
        video.save(video_path)

        # Tạo file audio từ video
        audio_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.wav")

        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            audio_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if not os.path.exists(audio_path):
            error = "Không tách được âm thanh từ video"
            return render_template("index.html", error=error)

        try:
            result = model.transcribe(
                audio_path,
                language="vi",
                fp16=False,
                condition_on_previous_text=False,
                verbose=False
            )

            text = result.get("text", "").strip()

            if mode == "subtitle":
                segments = result.get("segments", [])

                if not segments:
                    segments = split_text_to_fake_segments(text)

                subtitles = segments

                # Ghi file SRT
                srt_path = os.path.join(OUTPUT_FOLDER, "leviosa_subtitles.srt")
                with open(srt_path, "w", encoding="utf-8") as f:
                    for i, seg in enumerate(subtitles, 1):
                        f.write(f"{i}\n")
                        f.write(
                            f"{format_time(seg['start'])} --> {format_time(seg['end'])}\n"
                        )
                        f.write(seg["text"].strip() + "\n\n")

        except Exception as e:
            error = f"Lỗi Whisper: {str(e)}"

    return render_template(
        "index.html",
        text=text,
        subtitles=subtitles,
        mode=mode,
        error=error,
        video_path=video_path
    )


@app.route("/outputs/<filename>")
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
