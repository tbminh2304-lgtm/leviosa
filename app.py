import os, uuid
import whisper
import ffmpeg
from flask import Flask, render_template, request

app = Flask(__name__)

UPLOAD_DIR = "static/uploads"
OUTPUT_DIR = "static/outputs"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Whisper gốc – dùng medium cho tiếng Việt
model = whisper.load_model("medium")


def srt_time(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int((t - int(t)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        mode = request.form.get("mode", "text")
        video = request.files.get("video")

        if not video:
            return render_template("index.html", error="❌ Chưa chọn video")

        uid = str(uuid.uuid4())
        input_video = f"{UPLOAD_DIR}/{uid}.mp4"
        audio_file = f"{UPLOAD_DIR}/{uid}.wav"
        srt_file = f"{OUTPUT_DIR}/{uid}.srt"

        video.save(input_video)

        # 1️⃣ Tách audio
        ffmpeg.input(input_video).output(
            audio_file,
            ac=1,
            ar=16000,
            format="wav"
        ).run(overwrite_output=True)

        # 2️⃣ Whisper
        result = model.transcribe(audio_file, language="vi", verbose=False)
        segments = result["segments"]

        # 3️⃣ Text liền
        full_text = " ".join([s["text"].strip() for s in segments])

        # 4️⃣ Tạo SRT
        with open(srt_file, "w", encoding="utf-8") as f:
            for i, s in enumerate(segments, 1):
                f.write(
                    f"{i}\n"
                    f"{srt_time(s['start'])} --> {srt_time(s['end'])}\n"
                   f"{s['text'].strip()}\n\n"

                )

        return render_template(
            "index.html",
            mode=mode,
            text=full_text,
            subtitles=segments,
            video_id=uid
        )

    return render_template("index.html")


@app.route("/burn/<video_id>")
def burn(video_id):
    input_video = f"{UPLOAD_DIR}/{video_id}.mp4"
    srt_file = f"{OUTPUT_DIR}/{video_id}.srt"
    output_video = f"{OUTPUT_DIR}/{video_id}_sub.mp4"

    srt_ffmpeg = srt_file.replace("\\", "/")

    ffmpeg.input(input_video).output(
        output_video,
        vf=(
            f"subtitles='{srt_ffmpeg}':"
            "force_style='FontName=Arial,FontSize=26,"
            "PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=1'"
        ),
        vcodec="libx264",
        acodec="aac"
    ).run(overwrite_output=True)

    return render_template(
        "index.html",
        final_video_path=f"/static/outputs/{video_id}_sub.mp4"
    )


if __name__ == "__main__":
    if __name__ == "__main__":
    app.run()
