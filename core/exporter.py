"""Video export using ffmpeg (NVENC GPU-accelerated when available)"""
import numpy as np
import subprocess
import os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed


def _nvenc_available() -> bool:
    """Quick probe: ask ffmpeg to encode a 1-frame null video with h264_nvenc."""
    probe = subprocess.run(
        ["ffmpeg", "-hide_banner", "-f", "lavfi", "-i", "nullsrc=s=64x64:d=0.1",
         "-c:v", "h264_nvenc", "-f", "null", "-"],
        capture_output=True,
    )
    return probe.returncode == 0


def _render_frame_worker(args):
    """Top-level worker: render one frame and save it as PNG."""
    config, bars, path = args
    from core.renderer import render_frame
    img = render_frame(config, bars)
    img.save(path)


def export_video(config, frames_data: np.ndarray, progress_callback=None):
    """
    Export video to config.output_path.
    frames_data: shape (n_frames, n_bars)
    progress_callback: callable(int percent)
    """
    import tempfile, shutil

    fps = config.fps
    n_frames = len(frames_data)
    tmp_dir = tempfile.mkdtemp(prefix="banner_frames_")

    try:
        # Render all frames in parallel using multiple processes
        n_workers = min(os.cpu_count() or 4, n_frames)
        frame_args = [
            (config, frames_data[i], os.path.join(tmp_dir, f"frame_{i:06d}.png"))
            for i in range(n_frames)
        ]
        completed = 0
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            futures = {executor.submit(_render_frame_worker, arg): i
                       for i, arg in enumerate(frame_args)}
            for future in as_completed(futures):
                future.result()  # re-raise any exception from worker
                completed += 1
                if progress_callback:
                    progress_callback(int(completed / n_frames * 80))

        # Use ffmpeg to combine frames + audio
        out = config.output_path
        audio = config.audio_path

        use_nvenc = _nvenc_available()

        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", os.path.join(tmp_dir, "frame_%06d.png"),
        ]
        if audio and Path(audio).exists():
            cmd += ["-i", audio, "-shortest"]

        if use_nvenc:
            cmd += [
                "-c:v", "h264_nvenc",
                "-preset", "p4",      # balanced speed/quality (p1=fastest … p7=best)
                "-rc", "vbr",
                "-cq", "18",
                "-pix_fmt", "yuv420p",
            ]
        else:
            cmd += [
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "18",
                "-pix_fmt", "yuv420p",
            ]

        if audio and Path(audio).exists():
            cmd += ["-c:a", "aac", "-b:a", "192k"]

        cmd.append(out)

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed:\n{proc.stderr}")

        if progress_callback:
            progress_callback(100)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def export_preview_frame(config, bar_heights: np.ndarray, path: str):
    """Export a single preview frame as PNG"""
    from core.renderer import render_frame
    img = render_frame(config, bar_heights)
    img.save(path)
