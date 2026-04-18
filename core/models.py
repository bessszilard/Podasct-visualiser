"""Data models for the banner editor"""
from dataclasses import dataclass, field
from typing import Optional
from PySide6.QtGui import QColor


@dataclass
class TextElement:
    text: str = "Title Text"
    font_family: str = "Arial"
    font_size: int = 80
    bold: bool = True
    italic: bool = False
    color: str = "#F5C842"
    x: float = 0.05   # relative 0-1
    y: float = 0.08   # relative 0-1
    width: float = 0.9
    height: float = 0.35


@dataclass
class SubtitleElement:
    text: str = "Subtitle Text"
    font_family: str = "Arial"
    font_size: int = 40
    bold: bool = True
    italic: bool = True
    color: str = "#F5C842"
    x: float = 0.05
    y: float = 0.45
    width: float = 0.7
    height: float = 0.12


@dataclass
class SoundwaveElement:
    x: float = 0.03        # relative position
    y: float = 0.65
    width: float = 0.75
    height: float = 0.20
    color: str = "#F5C842"
    bar_count: int = 40
    style: str = "bars"    # bars, line, mirror


@dataclass
class ImageElement:
    path: str = ""
    x: float = 0.80
    y: float = 0.60
    width: float = 0.17
    height: float = 0.35
    opacity: float = 1.0


@dataclass
class BannerConfig:
    background_color: str = "#2D2D2D"
    audio_path: str = ""
    output_path: str = "output.mp4"
    fps: int = 30
    duration: float = 0.0   # 0 = use audio length

    title: TextElement = field(default_factory=TextElement)
    subtitle: SubtitleElement = field(default_factory=SubtitleElement)
    soundwave: SoundwaveElement = field(default_factory=SoundwaveElement)
    images: list = field(default_factory=list)
