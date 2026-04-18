"""Export dialog with progress bar"""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QLineEdit, QPushButton, QProgressBar,
                                QSpinBox, QFileDialog, QMessageBox)
from PySide6.QtCore import Qt, QThread, Signal


class ExportWorker(QThread):
    progress = Signal(int)
    finished = Signal()
    error = Signal(str)
    encoder = Signal(str)

    def __init__(self, config, frames_data):
        super().__init__()
        self.config = config
        self.frames_data = frames_data

    def run(self):
        try:
            from core.exporter import export_video, _nvenc_available
            self.encoder.emit("h264_nvenc (GPU)" if _nvenc_available() else "libx264 (CPU)")
            export_video(self.config, self.frames_data, self.progress.emit)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class ExportDialog(QDialog):
    def __init__(self, config, frames_data, parent=None):
        super().__init__(parent)
        self.config = config
        self.frames_data = frames_data
        self.setWindowTitle("Export Video")
        self.setModal(True)
        self.resize(500, 200)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)

        # Output path
        path_row = QHBoxLayout()
        self._path_edit = QLineEdit(self.config.output_path)
        browse_btn = QPushButton("…")
        browse_btn.setFixedWidth(30)
        browse_btn.clicked.connect(self._browse_output)
        path_row.addWidget(QLabel("Output:"))
        path_row.addWidget(self._path_edit)
        path_row.addWidget(browse_btn)
        lay.addLayout(path_row)

        # FPS
        fps_row = QHBoxLayout()
        fps_row.addWidget(QLabel("FPS:"))
        self._fps_spin = QSpinBox()
        self._fps_spin.setRange(1, 60)
        self._fps_spin.setValue(self.config.fps)
        fps_row.addWidget(self._fps_spin)
        fps_row.addStretch()
        lay.addLayout(fps_row)

        # Progress
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        lay.addWidget(self._progress)

        self._status_label = QLabel("Ready to export.")
        lay.addWidget(self._status_label)

        # Buttons
        btn_row = QHBoxLayout()
        self._export_btn = QPushButton("Export")
        self._export_btn.clicked.connect(self._start_export)
        cancel_btn = QPushButton("Close")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(self._export_btn)
        btn_row.addWidget(cancel_btn)
        lay.addLayout(btn_row)

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Video As", self._path_edit.text(),
            "MP4 Video (*.mp4)")
        if path:
            self._path_edit.setText(path)

    def _start_export(self):
        self.config.output_path = self._path_edit.text()
        self.config.fps = self._fps_spin.value()

        if not self.config.audio_path:
            QMessageBox.warning(self, "No Audio",
                                "Please select an audio file before exporting.")
            return

        self._export_btn.setEnabled(False)
        self._status_label.setText("Exporting…")

        self._worker = ExportWorker(self.config, self.frames_data)
        self._worker.progress.connect(self._progress.setValue)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.encoder.connect(lambda enc: self._status_label.setText(f"Exporting with {enc}…"))
        self._worker.start()

    def _on_done(self):
        self._status_label.setText(f"Done! Saved to: {self.config.output_path}")
        self._export_btn.setEnabled(True)

    def _on_error(self, msg):
        self._status_label.setText(f"Error: {msg}")
        self._export_btn.setEnabled(True)
        QMessageBox.critical(self, "Export Failed", msg)
