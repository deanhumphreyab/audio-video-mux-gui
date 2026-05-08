#!/usr/bin/env python3
"""
Audio / Video Mux GUI

A small Tkinter GUI that uses FFmpeg to:
  1. Replace a video's audio with an external audio file, without re-encoding video.
  2. Append an external audio file after the video's existing audio, without re-encoding video.

Requirements:
  - Python 3.9+
  - FFmpeg and FFprobe installed and available on PATH

Notes:
  - Video is always stream-copied with: -c:v copy
  - Audio is stream-copied when possible.
  - For maximum compatibility, output defaults to .mkv.
  - MP4 output is supported, but appending audio without audio re-encoding may fail if the original and appended audio codecs differ.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


APP_TITLE = "Audio / Video Mux GUI"

VIDEO_EXTENSIONS = (
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".ts", ".wmv"
)

AUDIO_EXTENSIONS = (
    ".wav", ".mp3", ".aac", ".m4a", ".flac", ".ogg", ".opus", ".wma"
)


def which_or_none(name: str) -> str | None:
    return shutil.which(name)


def run_command(command: list[str], log_queue: queue.Queue[str]) -> int:
    """Run a subprocess and stream output into the GUI log."""
    log_queue.put("\n$ " + " ".join(quote_arg(arg) for arg in command) + "\n")

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    assert process.stdout is not None
    for line in process.stdout:
        log_queue.put(line)

    process.wait()
    log_queue.put(f"\nProcess exited with code {process.returncode}\n")
    return process.returncode


def quote_arg(arg: str) -> str:
    if " " in arg or "\t" in arg:
        return f'"{arg}"'
    return arg


def ffprobe_streams(path: Path) -> dict:
    command = [
        "ffprobe",
        "-v", "error",
        "-show_streams",
        "-show_format",
        "-of", "json",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")
    return json.loads(result.stdout)


def has_audio_stream(path: Path) -> bool:
    data = ffprobe_streams(path)
    return any(stream.get("codec_type") == "audio" for stream in data.get("streams", []))


def choose_output_path(input_video: Path, mode: str) -> Path:
    suffix = ".mkv"
    stem_suffix = "_audio_replaced" if mode == "replace" else "_audio_appended"
    return input_video.with_name(input_video.stem + stem_suffix + suffix)


class MuxGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("860x620")
        self.minsize(780, 560)

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None

        self.video_path = tk.StringVar()
        self.audio_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.mode = tk.StringVar(value="replace")
        self.container_choice = tk.StringVar(value="mkv")
        self.audio_copy = tk.BooleanVar(value=True)
        self.keep_original_audio_when_replacing = tk.BooleanVar(value=False)

        self._build_ui()
        self._check_dependencies()
        self.after(100, self._drain_log_queue)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        title = ttk.Label(root, text=APP_TITLE, font=("Segoe UI", 16, "bold"))
        title.pack(anchor="w")

        description = ttk.Label(
            root,
            text=(
                "Replace a video's audio track or append extra audio while copying the video stream "
                "without recompression. Requires FFmpeg on PATH."
            ),
            wraplength=800,
        )
        description.pack(anchor="w", pady=(4, 14))

        file_box = ttk.LabelFrame(root, text="Files", padding=12)
        file_box.pack(fill="x")

        self._file_row(file_box, "Video file", self.video_path, self.browse_video, row=0)
        self._file_row(file_box, "Audio file", self.audio_path, self.browse_audio, row=1)
        self._file_row(file_box, "Output file", self.output_path, self.browse_output, row=2)

        options = ttk.LabelFrame(root, text="Operation", padding=12)
        options.pack(fill="x", pady=(12, 0))

        replace_radio = ttk.Radiobutton(
            options,
            text="Swap / replace video audio with selected audio",
            variable=self.mode,
            value="replace",
            command=self._mode_changed,
        )
        replace_radio.grid(row=0, column=0, sticky="w", padx=(0, 20))

        append_radio = ttk.Radiobutton(
            options,
            text="Append selected audio after existing video audio",
            variable=self.mode,
            value="append",
            command=self._mode_changed,
        )
        append_radio.grid(row=1, column=0, sticky="w", padx=(0, 20), pady=(6, 0))

        self.keep_original_check = ttk.Checkbutton(
            options,
            text="When replacing, keep original audio as an extra track instead of removing it",
            variable=self.keep_original_audio_when_replacing,
        )
        self.keep_original_check.grid(row=2, column=0, sticky="w", pady=(8, 0))

        container_frame = ttk.Frame(options)
        container_frame.grid(row=0, column=1, rowspan=3, sticky="nw")

        ttk.Label(container_frame, text="Output container").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(container_frame, text="MKV recommended", variable=self.container_choice, value="mkv", command=self._container_changed).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Radiobutton(container_frame, text="MP4", variable=self.container_choice, value="mp4", command=self._container_changed).grid(row=2, column=0, sticky="w")

        ttk.Checkbutton(
            container_frame,
            text="Copy audio streams when possible",
            variable=self.audio_copy,
        ).grid(row=3, column=0, sticky="w", pady=(8, 0))

        buttons = ttk.Frame(root)
        buttons.pack(fill="x", pady=(12, 0))

        self.run_button = ttk.Button(buttons, text="Run", command=self.run_job)
        self.run_button.pack(side="left")

        ttk.Button(buttons, text="Clear log", command=self.clear_log).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Probe video", command=self.probe_video).pack(side="left", padx=(8, 0))

        note = ttk.Label(
            root,
            text=(
                "Important: video is copied with -c:v copy. Appending audio requires compatible audio codecs "
                "for pure stream-copy concatenation. If it fails, disable audio copy to re-encode audio only."
            ),
            wraplength=820,
        )
        note.pack(anchor="w", pady=(10, 6))

        log_frame = ttk.LabelFrame(root, text="FFmpeg log", padding=8)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_frame, height=16, wrap="word", font=("Consolas", 10))
        self.log_text.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _file_row(self, parent: ttk.Frame, label: str, variable: tk.StringVar, command, row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(parent, text="Browse", command=command).grid(row=row, column=2, padx=(8, 0), pady=4)
        parent.grid_columnconfigure(1, weight=1)

    def _check_dependencies(self) -> None:
        missing = [name for name in ("ffmpeg", "ffprobe") if not which_or_none(name)]
        if missing:
            self.log(
                "Missing dependency: " + ", ".join(missing) + "\n"
                "Install FFmpeg and make sure ffmpeg.exe and ffprobe.exe are on PATH.\n"
            )
        else:
            self.log("FFmpeg and FFprobe found.\n")

    def browse_video(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose video file",
            filetypes=[("Video files", " ".join(f"*{ext}" for ext in VIDEO_EXTENSIONS)), ("All files", "*.*")],
        )
        if path:
            self.video_path.set(path)
            self._suggest_output_path()

    def browse_audio(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose audio file",
            filetypes=[("Audio files", " ".join(f"*{ext}" for ext in AUDIO_EXTENSIONS)), ("All files", "*.*")],
        )
        if path:
            self.audio_path.set(path)

    def browse_output(self) -> None:
        ext = ".mkv" if self.container_choice.get() == "mkv" else ".mp4"
        path = filedialog.asksaveasfilename(
            title="Choose output file",
            defaultextension=ext,
            filetypes=[("MKV file", "*.mkv"), ("MP4 file", "*.mp4"), ("All files", "*.*")],
        )
        if path:
            self.output_path.set(path)

    def _suggest_output_path(self) -> None:
        video = Path(self.video_path.get()) if self.video_path.get() else None
        if video and video.exists():
            out = choose_output_path(video, self.mode.get())
            if self.container_choice.get() == "mp4":
                out = out.with_suffix(".mp4")
            self.output_path.set(str(out))

    def _mode_changed(self) -> None:
        self._suggest_output_path()
        if self.mode.get() == "append":
            self.keep_original_check.state(["disabled"])
        else:
            self.keep_original_check.state(["!disabled"])

    def _container_changed(self) -> None:
        if self.output_path.get():
            ext = ".mkv" if self.container_choice.get() == "mkv" else ".mp4"
            self.output_path.set(str(Path(self.output_path.get()).with_suffix(ext)))

    def validate_inputs(self) -> tuple[Path, Path, Path] | None:
        video = Path(self.video_path.get().strip())
        audio = Path(self.audio_path.get().strip())
        output = Path(self.output_path.get().strip())

        if not video.exists():
            messagebox.showerror(APP_TITLE, "Choose a valid video file.")
            return None
        if not audio.exists():
            messagebox.showerror(APP_TITLE, "Choose a valid audio file.")
            return None
        if not output.parent.exists():
            messagebox.showerror(APP_TITLE, "Choose a valid output folder.")
            return None
        if output.exists():
            ok = messagebox.askyesno(APP_TITLE, "Output file already exists. Overwrite it?")
            if not ok:
                return None
        return video, audio, output

    def build_replace_command(self, video: Path, audio: Path, output: Path) -> list[str]:
        command = ["ffmpeg", "-y", "-i", str(video), "-i", str(audio)]

        if self.keep_original_audio_when_replacing.get():
            # Keep all original video streams and all audio streams.
            command += ["-map", "0:v", "-map", "0:a?", "-map", "1:a"]
        else:
            # Keep video from original and audio from selected audio file only.
            command += ["-map", "0:v", "-map", "1:a"]

        command += ["-c:v", "copy"]
        command += ["-c:a", "copy" if self.audio_copy.get() else "aac", "-shortest", str(output)]
        return command

    def build_append_command(self, video: Path, audio: Path, output: Path) -> list[str]:
        if not has_audio_stream(video):
            raise RuntimeError("The selected video does not appear to have an audio stream to append after.")

        if self.audio_copy.get():
            # Pure stream-copy append path. This works only when audio stream parameters are compatible.
            # The intermediate extraction keeps the original audio as-is, then concat demuxer joins it with the new audio.
            temp_dir = Path(tempfile.mkdtemp(prefix="mux_gui_"))
            original_audio = temp_dir / "original_audio.mka"
            concat_list = temp_dir / "concat.txt"

            extract_command = [
                "ffmpeg", "-y",
                "-i", str(video),
                "-vn",
                "-map", "0:a:0",
                "-c:a", "copy",
                str(original_audio),
            ]

            concat_list.write_text(
                "file " + ffconcat_escape(original_audio) + "\n" +
                "file " + ffconcat_escape(audio) + "\n",
                encoding="utf-8",
            )

            appended_audio = temp_dir / "appended_audio.mka"
            concat_command = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy",
                str(appended_audio),
            ]

            mux_command = [
                "ffmpeg", "-y",
                "-i", str(video),
                "-i", str(appended_audio),
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "copy",
                "-c:a", "copy",
                str(output),
            ]

            return ["__CHAIN__", str(temp_dir), json.dumps([extract_command, concat_command, mux_command])]

        # More reliable append path: re-encode audio only, copy video.
        # This keeps the video untouched while allowing audio files with different codecs/sample rates.
        filter_complex = "[0:a:0][1:a:0]concat=n=2:v=0:a=1[aout]"
        return [
            "ffmpeg", "-y",
            "-i", str(video),
            "-i", str(audio),
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            str(output),
        ]

    def run_job(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_TITLE, "A job is already running.")
            return

        inputs = self.validate_inputs()
        if inputs is None:
            return

        video, audio, output = inputs
        self.run_button.configure(state="disabled")
        self.log("\nStarting job...\n")

        def job() -> None:
            try:
                if self.mode.get() == "replace":
                    command = self.build_replace_command(video, audio, output)
                    code = run_command(command, self.log_queue)
                else:
                    command = self.build_append_command(video, audio, output)
                    if command[0] == "__CHAIN__":
                        temp_dir = Path(command[1])
                        chain = json.loads(command[2])
                        code = 0
                        try:
                            for step in chain:
                                code = run_command(step, self.log_queue)
                                if code != 0:
                                    break
                        finally:
                            shutil.rmtree(temp_dir, ignore_errors=True)
                    else:
                        code = run_command(command, self.log_queue)

                if code == 0:
                    self.log_queue.put("\nDone. Output created:\n" + str(output) + "\n")
                else:
                    self.log_queue.put("\nFailed. See FFmpeg log above.\n")
            except Exception as exc:
                self.log_queue.put("\nError: " + str(exc) + "\n")
            finally:
                self.log_queue.put("__ENABLE_RUN_BUTTON__")

        self.worker = threading.Thread(target=job, daemon=True)
        self.worker.start()

    def probe_video(self) -> None:
        if not self.video_path.get().strip():
            messagebox.showerror(APP_TITLE, "Choose a video first.")
            return
        path = Path(self.video_path.get().strip())
        if not path.exists():
            messagebox.showerror(APP_TITLE, "Video file does not exist.")
            return
        try:
            data = ffprobe_streams(path)
            pretty = json.dumps(data, indent=2)
            self.log("\nffprobe output:\n" + pretty + "\n")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def clear_log(self) -> None:
        self.log_text.delete("1.0", "end")

    def log(self, text: str) -> None:
        self.log_text.insert("end", text)
        self.log_text.see("end")

    def _drain_log_queue(self) -> None:
        try:
            while True:
                item = self.log_queue.get_nowait()
                if item == "__ENABLE_RUN_BUTTON__":
                    self.run_button.configure(state="normal")
                else:
                    self.log(item)
        except queue.Empty:
            pass
        self.after(100, self._drain_log_queue)


def ffconcat_escape(path: Path) -> str:
    # FFmpeg concat demuxer expects single quoted paths. Escape single quotes safely.
    text = str(path.resolve()).replace("\\", "/")
    return "'" + text.replace("'", "'\\''") + "'"


def main() -> None:
    app = MuxGui()
    app.mainloop()


if __name__ == "__main__":
    main()
