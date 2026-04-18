"""Audio analysis for soundwave visualization"""
import numpy as np
from pathlib import Path


def analyze_audio(audio_path: str, fps: int = 30, n_bars: int = 40):
    """
    Analyze audio file and return per-frame bar heights (0-1).
    Returns: (sample_rate, frames_data) where frames_data shape = (n_frames, n_bars)
    """
    try:
        import librosa
        y, sr = librosa.load(audio_path, sr=None, mono=True)
    except ImportError:
        # Fallback: use scipy/wave
        y, sr = _load_audio_fallback(audio_path)

    # Exact samples-per-frame at this sample rate and fps
    hop_length = max(1, sr // fps)
    n_frames = int(len(y) / sr * fps)

    # Use zero-padding for good FFT frequency resolution without look-ahead
    fft_size = max(2048, hop_length)

    frames_data = []
    global_max = 0.0

    for i in range(n_frames):
        start = i * hop_length
        end = min(start + hop_length, len(y))   # only this frame's audio
        chunk = y[start:end]
        if len(chunk) == 0:
            frames_data.append(np.zeros(n_bars))
            continue

        # FFT magnitude spectrum -> n_bars buckets
        # Zero-pad to fft_size for frequency resolution (no time look-ahead)
        fft = np.abs(np.fft.rfft(chunk, n=fft_size))
        fft = fft[:len(fft) // 2]   # keep lower half (more musical content)
        # bucket into n_bars
        bucket_size = max(1, len(fft) // n_bars)
        bar_vals = []
        for b in range(n_bars):
            s = b * bucket_size
            e = s + bucket_size
            bar_vals.append(float(np.mean(fft[s:e])))

        arr = np.array(bar_vals, dtype=float)
        frames_data.append(arr)
        frame_max = arr.max()
        if frame_max > global_max:
            global_max = frame_max

    # Normalize globally so amplitude reflects actual loudness across the track
    frames_array = np.array(frames_data)
    if global_max > 0:
        frames_array = frames_array / global_max
    # Apply perceptual curve
    frames_array = np.sqrt(frames_array)

    return sr, frames_array


def _load_audio_fallback(path: str):
    """Load audio using soundfile or wave module"""
    try:
        import soundfile as sf
        data, sr = sf.read(path, always_2d=False)
        if data.ndim > 1:
            data = data.mean(axis=1)
        return data.astype(np.float32), sr
    except Exception:
        pass

    # Try wave (only WAV)
    import wave, struct
    with wave.open(path, 'rb') as wf:
        sr = wf.getframerate()
        n = wf.getnframes()
        raw = wf.readframes(n)
        fmt = {1: 'b', 2: 'h', 4: 'i'}.get(wf.getsampwidth(), 'h')
        data = np.array(struct.unpack(f'{n * wf.getnchannels()}{fmt}', raw), dtype=float)
        if wf.getnchannels() > 1:
            data = data.reshape(-1, wf.getnchannels()).mean(axis=1)
        data = data / (2 ** (8 * wf.getsampwidth() - 1))
    return data.astype(np.float32), sr


def get_audio_duration(audio_path: str) -> float:
    """Return duration in seconds"""
    try:
        import librosa
        return float(librosa.get_duration(path=audio_path))
    except Exception:
        pass
    try:
        import soundfile as sf
        info = sf.info(audio_path)
        return info.duration
    except Exception:
        pass
    return 0.0
