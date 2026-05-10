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
The project focuses on preserving the original video stream where possible while changing the audio track.

What This Project Does
Provides a basic GUI workflow for selecting media files
Uses FFmpeg to process audio/video muxing
Supports replacing or appending audio depending on the workflow
Avoids unnecessary video re-encoding where possible
Helps make a repeatable media-restoration workflow easier to run
What This Project Does Not Do

This is not a full video editor.

It is not intended to replace professional editing software. The scope is intentionally narrow: make a specific FFmpeg audio/video workflow easier to use.

Tools and Dependencies
Python
FFmpeg
GitHub

FFmpeg must be installed and available on the system for the tool to work properly.

A common troubleshooting step is checking whether FFmpeg is installed and accessible from the command line:

ffmpeg -version

If that command does not work, FFmpeg may need to be installed or added to the system PATH.

Technical Focus

This project helped me practice:

working with external command-line tools
understanding dependencies
building a repeatable workflow
handling files and output paths
documenting setup requirements
thinking through basic troubleshooting steps
preserving video quality by avoiding unnecessary re-encoding
FFmpeg Concept

A key part of the workflow is copying the video stream instead of re-encoding it.

A simplified FFmpeg example looks like this:

ffmpeg -i input-video.mp4 -i new-audio.wav -c:v copy -c:a aac output-video.mp4

The important part is:

-c:v copy

That tells FFmpeg to copy the original video stream rather than re-encode it.

Learning Notes

This project connects to practical IT support learning because it involves:

identifying a workflow problem
choosing an appropriate tool
checking dependencies
testing outputs
documenting a repeatable process
troubleshooting when something does not work as expected

Even though the project is media-related, the process is similar to many IT support tasks: define the problem, check the environment, test the tool, confirm the result, and document the solution.

Future Improvements

Possible future improvements include:

clearer setup instructions
better error messages
progress feedback during processing
displaying the generated FFmpeg command before running it
support for more output options
better Windows and Linux testing notes
screenshots of the GUI workflow
Author

Dean Humphrey
Entry-Level IT Support and Networking Candidate
Edmonton, Alberta, Canada

Portfolio: https://deanhumphrey.ca

GitHub: https://github.com/deanhumphreyab
