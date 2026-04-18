"""Main application window"""
import numpy as np
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QScrollArea, QLabel, QSplitter, QFrame,
    QMessageBox, QSlider, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtGui import QIcon

from core.models import BannerConfig
from ui.preview_canvas import PreviewCanvas
from ui.panels import (BackgroundPanel, TextPanel, SoundwavePanel,
                       ImagesPanel, AudioPanel)
from ui.export_dialog import ExportDialog


def _fmt_ms(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"


class AnalyzeWorker(QThread):
    done = Signal(object)
    error = Signal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config

    def run(self):
        try:
            from core.audio_analyzer import analyze_audio
            sr, frames = analyze_audio(
                self.config.audio_path,
                self.config.fps,
                self.config.soundwave.bar_count
            )
            self.done.emit(frames)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Podcast Banner Editor")
        self.resize(1400, 860)
        self._config = BannerConfig()
        self._frames_data = None        # np.ndarray (n_frames, n_bars)
        self._player_duration = 0       # ms, set once media is loaded
        self._scrubber_dragging = False

        # ── media player ──────────────────────────────────────
        self._audio_out = QAudioOutput()
        self._audio_out.setVolume(1.0)
        self._player = QMediaPlayer()
        self._player.setAudioOutput(self._audio_out)
        self._player.playbackStateChanged.connect(self._on_playback_state)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.positionChanged.connect(self._on_position_changed)

        # ── sync timer (fires at ~30 fps) ─────────────────────
        self._sync_timer = QTimer()
        self._sync_timer.setInterval(33)
        self._sync_timer.timeout.connect(self._sync_frame)

        self._build_ui()
        self._apply_dark_theme()

    # ─────────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left panel ────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(320)
        scroll.setFrameShape(QFrame.NoFrame)
        panel_widget = QWidget()
        panel_lay = QVBoxLayout(panel_widget)
        panel_lay.setSpacing(6)
        panel_lay.setContentsMargins(8, 8, 8, 8)

        self._audio_panel = AudioPanel(self._config)
        self._audio_panel.changed.connect(self._on_audio_changed)
        panel_lay.addWidget(self._audio_panel)

        self._bg_panel = BackgroundPanel(self._config)
        self._bg_panel.changed.connect(self._refresh_preview)
        panel_lay.addWidget(self._bg_panel)

        self._title_panel = TextPanel("Title", self._config.title)
        self._title_panel.changed.connect(self._refresh_preview)
        panel_lay.addWidget(self._title_panel)

        self._sub_panel = TextPanel("Subtitle", self._config.subtitle)
        self._sub_panel.changed.connect(self._refresh_preview)
        panel_lay.addWidget(self._sub_panel)

        self._sw_panel = SoundwavePanel(self._config.soundwave)
        self._sw_panel.changed.connect(self._refresh_preview)
        panel_lay.addWidget(self._sw_panel)

        self._img_panel = ImagesPanel(self._config)
        self._img_panel.changed.connect(self._refresh_preview)
        panel_lay.addWidget(self._img_panel)

        panel_lay.addStretch()

        export_btn = QPushButton("Export Video…")
        export_btn.setFixedHeight(38)
        export_btn.clicked.connect(self._export)
        export_btn.setStyleSheet(
            "background:#e8a020; color:#000; font-weight:bold; "
            "border-radius:5px; font-size:14px;")
        panel_lay.addWidget(export_btn)

        scroll.setWidget(panel_widget)
        root.addWidget(scroll)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedWidth(1)
        root.addWidget(sep)

        # ── Right: preview + transport ────────────────────────
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(8, 8, 8, 8)
        right_lay.setSpacing(6)

        self._canvas = PreviewCanvas(self._config)
        right_lay.addWidget(self._canvas, 1)

        # Analyze button
        self._analyze_btn = QPushButton("Analyze Audio")
        self._analyze_btn.setFixedHeight(30)
        self._analyze_btn.clicked.connect(self._analyze_audio)
        self._analyze_btn.setStyleSheet(
            "background:#3a7ebf; color:#fff; font-weight:bold; border-radius:4px;")
        right_lay.addWidget(self._analyze_btn)

        # ── Scrubber ──────────────────────────────────────────
        scrubber_row = QHBoxLayout()
        self._time_label = QLabel("0:00")
        self._time_label.setFixedWidth(40)
        self._time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._scrubber = QSlider(Qt.Horizontal)
        self._scrubber.setRange(0, 1000)
        self._scrubber.setValue(0)
        self._scrubber.sliderPressed.connect(self._scrubber_pressed)
        self._scrubber.sliderReleased.connect(self._scrubber_released)
        self._scrubber.sliderMoved.connect(self._scrubber_moved)

        self._dur_label = QLabel("0:00")
        self._dur_label.setFixedWidth(40)
        self._dur_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        scrubber_row.addWidget(self._time_label)
        scrubber_row.addWidget(self._scrubber)
        scrubber_row.addWidget(self._dur_label)
        right_lay.addLayout(scrubber_row)

        # ── Transport buttons ─────────────────────────────────
        transport = QHBoxLayout()
        transport.setSpacing(8)

        self._play_btn = QPushButton("▶  Play")
        self._play_btn.setFixedHeight(36)
        self._play_btn.setEnabled(False)
        self._play_btn.clicked.connect(self._toggle_play)
        self._play_btn.setStyleSheet(
            "background:#2e7d32; color:#fff; font-weight:bold; "
            "border-radius:5px; font-size:13px;")

        self._stop_btn = QPushButton("■  Stop")
        self._stop_btn.setFixedHeight(36)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_playback)
        self._stop_btn.setStyleSheet(
            "background:#555; color:#fff; font-weight:bold; "
            "border-radius:5px; font-size:13px;")

        # Volume slider
        vol_label = QLabel("Vol")
        vol_label.setFixedWidth(24)
        self._vol_slider = QSlider(Qt.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(100)
        self._vol_slider.setFixedWidth(90)
        self._vol_slider.valueChanged.connect(
            lambda v: self._audio_out.setVolume(v / 100))

        transport.addWidget(self._play_btn)
        transport.addWidget(self._stop_btn)
        transport.addStretch()
        transport.addWidget(vol_label)
        transport.addWidget(self._vol_slider)
        right_lay.addLayout(transport)

        root.addWidget(right, 1)

    # ─────────────────────────────────────────────────────────
    # Audio / analysis
    # ─────────────────────────────────────────────────────────
    def _on_audio_changed(self):
        self._stop_playback()
        self._frames_data = None
        self._analyze_btn.setText("Analyze Audio")
        self._play_btn.setEnabled(False)
        self._stop_btn.setEnabled(False)
        self._scrubber.setValue(0)
        self._time_label.setText("0:00")
        self._dur_label.setText("0:00")
        # Load into media player for playback
        self._player.setSource(QUrl.fromLocalFile(self._config.audio_path))

    def _analyze_audio(self):
        if not self._config.audio_path:
            QMessageBox.information(self, "No Audio",
                                    "Please select an audio file first.")
            return
        self._analyze_btn.setEnabled(False)
        self._analyze_btn.setText("Analyzing…")
        self._worker = AnalyzeWorker(self._config)
        self._worker.done.connect(self._on_analysis_done)
        self._worker.error.connect(self._on_analysis_error)
        self._worker.start()

    def _on_analysis_done(self, frames: np.ndarray):
        self._frames_data = frames
        self._analyze_btn.setEnabled(True)
        self._analyze_btn.setText("Re-analyze Audio")
        mid = frames[len(frames) // 2]
        self._canvas._idle_timer.stop()
        self._canvas.set_bar_heights(mid)
        self._play_btn.setEnabled(True)
        self._stop_btn.setEnabled(True)

    def _on_analysis_error(self, msg: str):
        self._analyze_btn.setEnabled(True)
        self._analyze_btn.setText("Analyze Audio")
        QMessageBox.critical(self, "Analysis Failed", msg)

    # ─────────────────────────────────────────────────────────
    # Transport controls
    # ─────────────────────────────────────────────────────────
    def _toggle_play(self):
        if self._player.playbackState() == QMediaPlayer.PlayingState:
            self._player.pause()
        else:
            self._player.play()
            self._sync_timer.start()

    def _stop_playback(self):
        self._player.stop()
        self._sync_timer.stop()
        self._play_btn.setText("▶  Play")
        self._scrubber.setValue(0)
        self._time_label.setText("0:00")
        # Restore idle animation if no frame to show
        if self._frames_data is None:
            self._canvas._idle_timer.start()

    def _on_playback_state(self, state):
        if state == QMediaPlayer.PlayingState:
            self._play_btn.setText("⏸  Pause")
            self._sync_timer.start()
        elif state == QMediaPlayer.PausedState:
            self._play_btn.setText("▶  Play")
            self._sync_timer.stop()
        else:  # StoppedState
            self._play_btn.setText("▶  Play")
            self._sync_timer.stop()

    def _on_duration_changed(self, duration_ms: int):
        self._player_duration = duration_ms
        self._dur_label.setText(_fmt_ms(duration_ms))

    def _on_position_changed(self, pos_ms: int):
        if self._scrubber_dragging or self._player_duration == 0:
            return
        ratio = pos_ms / self._player_duration
        self._scrubber.setValue(int(ratio * 1000))
        self._time_label.setText(_fmt_ms(pos_ms))

    # ─────────────────────────────────────────────────────────
    # Scrubber interaction
    # ─────────────────────────────────────────────────────────
    def _scrubber_pressed(self):
        self._scrubber_dragging = True

    def _scrubber_released(self):
        self._scrubber_dragging = False
        if self._player_duration > 0:
            ms = int(self._scrubber.value() / 1000 * self._player_duration)
            self._player.setPosition(ms)
            self._time_label.setText(_fmt_ms(ms))
            self._sync_frame(ms)  # snap canvas immediately

    def _scrubber_moved(self, value: int):
        if self._player_duration > 0:
            ms = int(value / 1000 * self._player_duration)
            self._time_label.setText(_fmt_ms(ms))
            self._sync_frame(ms)  # live preview while dragging

    # ─────────────────────────────────────────────────────────
    # Frame sync
    # ─────────────────────────────────────────────────────────
    def _sync_frame(self, override_ms: int = None):
        if self._frames_data is None:
            return
        pos_ms = override_ms if override_ms is not None else self._player.position()
        fps = self._config.fps
        frame_idx = int(pos_ms / 1000 * fps)
        frame_idx = max(0, min(frame_idx, len(self._frames_data) - 1))
        self._canvas.set_bar_heights(self._frames_data[frame_idx])

    # ─────────────────────────────────────────────────────────
    # Preview / export
    # ─────────────────────────────────────────────────────────
    def _refresh_preview(self):
        self._canvas.update()

    def _export(self):
        if self._frames_data is None:
            if self._config.audio_path:
                reply = QMessageBox.question(
                    self, "Audio Not Analyzed",
                    "Audio has not been analyzed yet. Analyze now before exporting?",
                    QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self._analyze_audio()
                    return
            else:
                QMessageBox.information(
                    self, "No Audio",
                    "Please select an audio file and analyze it before exporting.")
                return
        dlg = ExportDialog(self._config, self._frames_data, self)
        dlg.exec()

    # ─────────────────────────────────────────────────────────
    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background: #1e1e1e;
                color: #dddddd;
            }
            QGroupBox {
                border: 1px solid #444;
                border-radius: 5px;
                margin-top: 6px;
                font-weight: bold;
                color: #aaaaaa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background: #2d2d2d;
                border: 1px solid #555;
                border-radius: 3px;
                color: #eeeeee;
                padding: 2px 4px;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #5a9fd4;
            }
            QPushButton {
                background: #3c3c3c;
                border: 1px solid #555;
                border-radius: 4px;
                color: #eeeeee;
                padding: 4px 10px;
            }
            QPushButton:hover { background: #4a4a4a; }
            QPushButton:pressed { background: #2a2a2a; }
            QScrollArea { background: #1e1e1e; border: none; }
            QListWidget {
                background: #2d2d2d;
                border: 1px solid #444;
                border-radius: 3px;
            }
            QProgressBar {
                border: 1px solid #555;
                border-radius: 3px;
                background: #2d2d2d;
            }
            QProgressBar::chunk { background: #3a7ebf; border-radius: 2px; }
            QSlider::groove:horizontal {
                height: 4px;
                background: #444;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
                background: #5a9fd4;
            }
            QSlider::sub-page:horizontal {
                background: #5a9fd4;
                border-radius: 2px;
            }
        """)
