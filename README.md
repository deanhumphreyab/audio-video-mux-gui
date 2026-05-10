# Audio and Video Muxing GUI

A small Python and FFmpeg project for replacing or appending audio in video files without re-encoding the video stream.

This project was built as a practical learning exercise in GUI workflow design, file handling, external dependencies, media troubleshooting, and technical documentation.

---

## Purpose

Sometimes a video file does not need to be re-edited or re-encoded, but the audio track needs to be replaced with a corrected, restored, or improved version.

This tool is meant to make that workflow easier by providing a simple GUI around an FFmpeg-based process.

The basic goal is:

```text
Original video file + new audio file = video file with updated audio
