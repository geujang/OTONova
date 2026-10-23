"""Cached waveform/spectrogram background with low-cost draggable overlays."""

from pathlib import Path
import ui_settings as ui
import numpy as np
from scipy.signal import stft
from PySide6.QtCore import Qt, Signal, QRectF, QLineF, QThread
from PySide6.QtGui import QColor, QPainter, QPen, QImage, QPixmap, QPainterPath
from PySide6.QtWidgets import QWidget

MAX_HZ = 15000.0

SPECTRUM_PALETTES = {
    "classic": (
        "기본",
        [
            [8, 14, 29],
            [36, 32, 80],
            [65, 72, 151],
            [21, 169, 182],
            [243, 163, 61],
            [255, 242, 161],
        ],
    ),
    "purple": (
        "보라 · 분홍",
        [
            [15, 5, 30],
            [48, 12, 86],
            [104, 25, 153],
            [183, 55, 190],
            [244, 136, 206],
            [255, 244, 247],
        ],
    ),
    "fire": (
        "불꽃",
        [
            [0, 0, 4],
            [58, 9, 88],
            [126, 30, 108],
            [201, 62, 63],
            [249, 142, 9],
            [252, 255, 164],
        ],
    ),
    "ocean": (
        "바다",
        [
            [5, 10, 40],
            [20, 45, 110],
            [20, 100, 170],
            [20, 180, 190],
            [120, 230, 190],
            [245, 255, 210],
        ],
    ),
    "rainbow": (
        "무지개",
        [
            [35, 20, 75],
            [45, 65, 185],
            [20, 170, 220],
            [40, 210, 105],
            [235, 220, 40],
            [250, 90, 20],
            [180, 10, 50],
        ],
    ),
    "gray": ("흑백", [[0, 0, 0], [255, 255, 255]]),
}


def spectrum_levels(audio, sr):
    """Cache intensity independently of the selected color palette."""
    nfft = min(4096, max(1, 2 ** int(np.floor(np.log2(max(1, len(audio)))))))
    hop = min(128, max(1, nfft // 4))
    freq, times, spectrum = stft(
        audio.astype(np.float32),
        fs=sr,
        nperseg=nfft,
        noverlap=nfft - hop,
        boundary="zeros",
        padded=True,
    )
    mask = freq <= MAX_HZ
    db = 20 * np.log10(np.maximum(np.abs(spectrum[mask]), 1e-10))
    peak = max(float(db.max()), -100)
    level = np.clip((db - (peak - 80)) / 80, 0, 1)
    return (
        np.ascontiguousarray(np.rint(level[::-1] * 1023).astype(np.uint16)),
        float(freq[mask][-1]),
        times,
    )


def colorize_spectrum(levels, palette="classic"):
    colors = np.array(SPECTRUM_PALETTES[palette][1], dtype=float)
    points = np.linspace(0, 1, len(colors))
    lookup = np.stack(
        [np.interp(np.linspace(0, 1, 1024), points, colors[:, i]) for i in range(3)],
        axis=-1,
    ).astype(np.uint8)
    return np.ascontiguousarray(lookup[levels])


def make_spectrogram(audio, sr, palette="classic"):
    levels, high_hz, times = spectrum_levels(audio, sr)
    return colorize_spectrum(levels, palette), high_hz, times


def rms_energy(audio, sr):
    """20 ms RMS windows every 10 ms, expressed as absolute dBFS."""
    if len(audio) == 0:
        return np.array([]), np.array([])
    width = max(1, round(sr * 0.02))
    hop = max(1, round(sr * 0.01))
    starts = np.arange(0, len(audio), hop)
    ends = np.minimum(starts + width, len(audio))
    summed = np.concatenate(([0.0], np.cumsum(np.square(audio, dtype=np.float64))))
    rms = np.sqrt(np.maximum(0, (summed[ends] - summed[starts]) / (ends - starts)))
    return (starts + ends) / (2 * sr), 20 * np.log10(np.maximum(rms, 1e-6))


class FeatureLoader(QThread):
    ready = Signal(str, object)
    failed = Signal(str, str)

    def __init__(self, path, cache_folder=None, expected_signature=None):
        super().__init__()
        self.path = path
        self.cache_folder = cache_folder
        self.expected_signature = expected_signature

    def run(self):
        try:
            from audio_cache import get

            self.ready.emit(
                str(self.path),
                get(self.path, self.cache_folder, self.expected_signature),
            )
        except Exception as exc:
            self.failed.emit(str(self.path), str(exc))


class AudioEditor(QWidget):
    segmentRequested = Signal(float, float)
    otoMoved = Signal(int, float)
    boundaryMoved = Signal(int, float)
    editStarted = Signal()
    editFinished = Signal()
    viewChanged = Signal(float, float)
    boundarySelected = Signal(int, float)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(400)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setToolTip(
            "음소 경계선 드래그: 실시간 원설 · 휠: 확대/축소 · 아래 스크롤바: 이동"
        )
        self.samples = None
        self.duration = 1.0
        self.spans = []
        self.row = None
        self.path = None
        self.image = None
        self.spectrum_levels = None
        self.spectrum_palette = None
        self.energy_times = np.array([])
        self.energy_db = np.array([])
        self.high_hz = MAX_HZ
        self.start = 0.0
        self.length = 1.0
        self.dragging = None
        self.oto_dragging = None
        self.keyboard_marker = None
        self.stage = 1
        self.pointer_x = None
        self.hover = None
        self.selected_boundary = None
        self.editable = True
        self._background = None
        self._background_key = None
        self.background_builds = 0
        self.async_loading = False
        self.cache_folder = None
        self._load_jobs = []
        self.approved_signatures = {}
        self._load_revision = 0

    def clear(self):
        self._load_revision += 1
        self.samples = None
        self.path = None
        self.image = None
        self.spectrum_levels = None
        self.spectrum_palette = None
        self.energy_times = np.array([])
        self.energy_db = np.array([])
        self.spans = []
        self.row = None
        self._background = None
        self._background_key = None
        self.update()

    def load(self, path, spans, row):
        path = Path(path)
        self.spans = spans
        self.row = row
        if self.path != path:
            self._load_revision += 1
            from audio_cache import get, peek

            expected = self.approved_signatures.get(str(path.resolve()))
            self.path = path
            data = peek(path, expected)
            if data is not None:
                self._apply_features(str(path), data)
            elif self.async_loading:
                self.samples = None
                self.image = None
                self._background_key = None
                job = FeatureLoader(path, self.cache_folder, expected)
                self._load_jobs.append(job)
                revision = self._load_revision
                job.ready.connect(
                    lambda p, d, r=revision: (
                        self._apply_features(p, d) if r == self._load_revision else None
                    )
                )
                job.failed.connect(self._feature_failed)
                job.finished.connect(
                    lambda j=job: (
                        self._load_jobs.remove(j) if j in self._load_jobs else None
                    )
                )
                job.start()
            else:
                self._apply_features(str(path), get(path, self.cache_folder, expected))
        self.viewChanged.emit(self.start, self.length)
        self.update()

    def _feature_failed(self, path, error):
        if self.path == Path(path):
            self.empty_message = error
            self.update()

    def _apply_features(self, path, data):
        if self.path != Path(path):
            return
        self.samples = data["samples"]
        self.sample_rate = int(data["sample_rate"])
        self.duration = len(self.samples) / self.sample_rate
        self.wave_gain = 1 / max(float(np.max(np.abs(self.samples))), 1e-6)
        self.spectrum_levels = data["levels"]
        self.high_hz = float(data["high_hz"])
        self.energy_times = data["energy_times"]
        self.energy_db = data["energy_db"]
        self.spectrum_palette = None
        self.update_spectrum_palette()
        self.start = 0.0
        self.length = self.duration
        self.selected_boundary = None
        self._background_key = None
        self.viewChanged.emit(self.start, self.length)
        self.update()

    def update_spectrum_palette(self):
        palette = getattr(ui, "spectrum_palette", "classic")
        if self.spectrum_levels is None or palette == self.spectrum_palette:
            return
        rgb = colorize_spectrum(self.spectrum_levels, palette)
        self.image = QImage(
            rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format_RGB888
        ).copy()
        self.spectrum_palette = palette
        self._background_key = None
        self.update()

    def segment_at(self, seconds):
        if self.samples is None:
            return None
        if self.stage == 2 and self.row:
            boundaries = self.row["absolute"]
        else:
            boundaries = [v for begin, end, phone in self.spans for v in (begin, end)]
        points = sorted(
            set(
                [0.0, self.duration]
                + [max(0.0, min(self.duration, float(t))) for t in boundaries]
            )
        )
        for begin, end in zip(points, points[1:]):
            if begin <= seconds < end or seconds == self.duration == end:
                return begin, end
        return None

    def plot_rects(self):
        left, right = 68, 15
        width = max(1, self.width() - left - right)
        wave = QRectF(left, 32, width, max(70, self.height() * 0.28))
        top = wave.bottom() + 110
        spec = QRectF(left, top, width, max(80, self.height() - top - 68))
        return wave, spec

    def time_x(self, t):
        wave, _ = self.plot_rects()
        return wave.left() + (t - self.start) / self.length * wave.width()

    def x_time(self, x):
        wave, _ = self.plot_rects()
        return self.start + (x - wave.left()) / wave.width() * self.length

    def set_view(self, start, length):
        self.length = max(0.05, min(self.duration, length))
        self.start = max(0, min(self.duration - self.length, start))
        self.viewChanged.emit(self.start, self.length)
        self.update()

    def zoom(self, factor, anchor=None):
        if self.samples is None:
            return
        anchor = self.start + self.length * 0.5 if anchor is None else anchor
        ratio = (anchor - self.start) / self.length
        length = max(0.05, min(self.duration, self.length / factor))
        self.set_view(anchor - ratio * length, length)

    def reset_view(self):
        self.set_view(0, self.duration)

    def enterEvent(self, event):
        if self.editable:
            self.setFocus()
        super().enterEvent(event)

    def set_stage(self, stage):
        self.stage = stage
        self.dragging = None
        self.oto_dragging = None
        self.keyboard_marker = None
        self.hover = None
        self.update()

    def ordered_markers(self):
        return (
            sorted(range(5), key=lambda i: (self.row["absolute"][i], i))
            if self.row
            else []
        )

    def nearest_marker(self, x):
        distance, index = (
            min(
                (
                    (abs(self.time_x(t) - x), i)
                    for i, t in enumerate(self.row["absolute"])
                ),
                default=(999, None),
            )
            if self.row
            else (999, None)
        )
        return index if distance <= 9 else None

    def keyPressEvent(self, event):
        if (
            self.stage == 2
            and self.editable
            and self.row
            and Qt.Key_1 <= event.key() <= Qt.Key_5
        ):
            if event.isAutoRepeat():
                return
            if self.keyboard_marker is not None:
                return
            if self.pointer_x is None:
                return
            self.keyboard_marker = self.ordered_markers()[event.key() - Qt.Key_1]
            self.editStarted.emit()
            self.otoMoved.emit(self.keyboard_marker, self.x_time(self.pointer_x))
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if Qt.Key_1 <= event.key() <= Qt.Key_5 and self.keyboard_marker is not None:
            if event.isAutoRepeat():
                return
            self.keyboard_marker = None
            self.editFinished.emit()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def focusOutEvent(self, event):
        if self.keyboard_marker is not None:
            self.keyboard_marker = None
            self.editFinished.emit()
        super().focusOutEvent(event)

    def nearest_boundary(self, x):
        candidates = [
            (abs(self.time_x(self.spans[i][0]) - x), i)
            for i in range(1, len(self.spans))
            if self.start <= self.spans[i][0] <= self.start + self.length
        ]
        distance, index = min(candidates, default=(999, None))
        return index if distance <= 9 else None

    def mousePressEvent(self, event):
        wave, spec = self.plot_rects()
        if self.samples is None:
            return
        if event.button() == Qt.RightButton:
            pos = event.position()
            if (
                wave.left() <= pos.x() <= wave.right()
                and wave.top() <= pos.y() <= spec.bottom()
            ):
                segment = self.segment_at(self.x_time(pos.x()))
                if segment:
                    self.segmentRequested.emit(*segment)
            event.accept()
            return
        if event.button() != Qt.LeftButton or not self.editable:
            return
        pos = event.position()
        self.setFocus()
        self.pointer_x = pos.x()
        if (
            not wave.left() <= pos.x() <= wave.right()
            or not 0 <= pos.y() <= spec.bottom()
        ):
            return
        if self.stage == 2:
            index = self.nearest_marker(pos.x())
            if index is not None:
                self.oto_dragging = index
                self.editStarted.emit()
                self.setCursor(Qt.SizeHorCursor)
            return
        index = self.nearest_boundary(pos.x())
        if index is not None:
            self.dragging = index
            self.selected_boundary = index
            self.editStarted.emit()
            self.boundarySelected.emit(index, self.spans[index][0])
            self.setCursor(Qt.SizeHorCursor)
            self.update()

    def mouseMoveEvent(self, event):
        if self.samples is None:
            return
        self.pointer_x = event.position().x()
        if self.stage == 2:
            marker = (
                self.keyboard_marker
                if self.keyboard_marker is not None
                else self.oto_dragging
            )
            if marker is not None:
                self.otoMoved.emit(marker, self.x_time(self.pointer_x))
            else:
                self.setCursor(
                    Qt.SizeHorCursor
                    if self.nearest_marker(self.pointer_x) is not None
                    else Qt.ArrowCursor
                )
            return
        if self.dragging is not None:
            self.boundaryMoved.emit(self.dragging, self.x_time(event.position().x()))
        else:
            hover = (
                self.nearest_boundary(event.position().x()) if self.editable else None
            )
            if hover != self.hover:
                self.hover = hover
                self.setCursor(
                    Qt.SizeHorCursor if self.hover is not None else Qt.ArrowCursor
                )
                self.update()

    def mouseReleaseEvent(self, event):
        if self.oto_dragging is not None:
            self.oto_dragging = None
            self.editFinished.emit()
            self.update()
            return
        if self.dragging is not None:
            self.dragging = None
            self.editFinished.emit()
            self.update()

    def wheelEvent(self, event):
        if self.samples is not None:
            self.zoom(
                1.35 if event.angleDelta().y() > 0 else 1 / 1.35,
                self.x_time(event.position().x()),
            )
        event.accept()

    def _draw_background(self, p):
        p.fillRect(self.rect(), QColor(ui.colors()["bg"]))
        wave, spec = self.plot_rects()
        p.fillRect(wave, QColor(ui.colors()["panel"]))
        p.fillRect(spec, QColor(ui.colors()["panel"]))
        p.setPen(QColor(ui.colors()["muted"]))
        p.drawText(5, int(wave.top() + 15), ui.translate("파형"))
        p.drawText(
            int(spec.left()),
            int(spec.top() - 9),
            ui.translate("스펙토그램") + " · 0–15,000 Hz",
        )
        n = len(self.samples)
        p.save()
        p.setClipRect(wave)
        p.setPen(QPen(QColor(ui.colors()["wave"]), 1))
        center = wave.center().y()
        amplitude = wave.height() * 0.44 * self.wave_gain
        # Aggregate the visible audio once per view/resize, including HiDPI pixels.
        columns = max(1, int(wave.width() * self.devicePixelRatioF()))
        edges = np.floor(
            (self.start + np.arange(columns + 1) / columns * self.length)
            * self.sample_rate
        ).astype(np.int64)
        starts = np.clip(edges[:-1], 0, n - 1)
        end = min(n, max(int(starts[-1]) + 1, int(edges[-1])))
        unique, inverse = np.unique(starts, return_inverse=True)
        audio = self.samples[int(unique[0]) : end]
        minimum = np.minimum.reduceat(audio, unique - unique[0])[inverse]
        maximum = np.maximum.reduceat(audio, unique - unique[0])[inverse]
        p.drawLines(
            [
                QLineF(
                    wave.left() + i / columns * wave.width(),
                    center - hi * amplitude,
                    wave.left() + i / columns * wave.width(),
                    center - lo * amplitude,
                )
                for i, (lo, hi) in enumerate(zip(minimum, maximum))
            ]
        )
        p.restore()
        energy = QRectF(wave.left(), wave.bottom() + 30, wave.width(), 48)
        p.fillRect(energy, QColor(ui.colors()["panel"]))
        p.setPen(QColor(ui.colors()["muted"]))
        p.drawText(5, int(energy.top() + 13), ui.translate("에너지"))
        p.drawText(5, int(energy.bottom()), "-60 dBFS")
        p.drawText(int(energy.left()), int(energy.top() - 5), "RMS · 0 dBFS")
        visible = np.flatnonzero(
            (self.energy_times >= self.start)
            & (self.energy_times <= self.start + self.length)
        )
        if len(visible):
            visible = visible[
                :: max(1, len(visible) // max(1, int(energy.width() * 2)))
            ]
            curve = QPainterPath()
            for n, index in enumerate(visible):
                x = self.time_x(self.energy_times[index])
                y = (
                    energy.bottom()
                    - float(np.clip((self.energy_db[index] + 60) / 60, 0, 1))
                    * energy.height()
                )
                if n == 0:
                    curve.moveTo(x, y)
                else:
                    curve.lineTo(x, y)
            p.setPen(QPen(QColor("#ed8bdc" if ui.theme == "dark" else "#ac238c"), 1.5))
            p.drawPath(curve)
        if self.image:
            height = spec.height() * min(MAX_HZ, self.high_hz) / MAX_HZ
            target = QRectF(spec.left(), spec.bottom() - height, spec.width(), height)
            source = QRectF(
                self.start / self.duration * self.image.width(),
                0,
                self.length / self.duration * self.image.width(),
                self.image.height(),
            )
            p.drawImage(target, self.image, source)
        for hz in [15000, 10000, 5000, 0]:
            y = spec.bottom() - hz / MAX_HZ * spec.height()
            p.setPen(QColor(ui.colors()["muted"]))
            p.drawText(5, int(y + 5), f"{hz:,}")
            p.setPen(QColor(110, 130, 150, 65))
            p.drawLine(int(spec.left()), int(y), int(spec.right()), int(y))

    def _ensure_background(self):
        ratio = self.devicePixelRatioF()
        key = (
            self.path,
            self.width(),
            self.height(),
            ratio,
            self.start,
            self.length,
            ui.theme,
            ui.language,
        )
        if key != self._background_key:
            image = QPixmap(
                max(1, round(self.width() * ratio)),
                max(1, round(self.height() * ratio)),
            )
            image.setDevicePixelRatio(ratio)
            painter = QPainter(image)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            self._draw_background(painter)
            painter.end()
            self._background = image
            self._background_key = key
            self.background_builds += 1

    def paintEvent(self, event):
        p = QPainter(self)
        if self.samples is None:
            p.fillRect(self.rect(), QColor(ui.colors()["bg"]))
            p.setPen(QColor(ui.colors()["text"]))
            p.drawText(
                self.rect(),
                Qt.AlignCenter,
                ui.translate(
                    getattr(
                        self,
                        "empty_message",
                        "원설 행 선택 → 음소 경계 드래그 → 즉시 재계산",
                    )
                ),
            )
            return
        self._ensure_background()
        p.drawPixmap(0, 0, self._background)
        wave, spec = self.plot_rects()
        # Discarded audio shading, then phoneme boundaries behind oto markers.
        p.save()
        p.setClipRect(
            QRectF(wave.left(), wave.top(), wave.width(), spec.bottom() - wave.top())
        )
        offset, overlap, pre, fixed, cutoff = (
            self.row["absolute"] if self.row else [0, 0, 0, 0, self.duration]
        )
        plot_height = spec.bottom() - wave.top()
        offset_x = max(wave.left(), min(wave.right(), self.time_x(offset)))
        cutoff_x = max(wave.left(), min(wave.right(), self.time_x(cutoff)))
        if self.stage == 2 and self.row:
            p.fillRect(
                QRectF(wave.left(), wave.top(), offset_x - wave.left(), plot_height),
                QColor(255, 215, 0, 48),
            )
            p.fillRect(
                QRectF(cutoff_x, wave.top(), wave.right() - cutoff_x, plot_height),
                QColor(255, 255, 255, 48),
            )
        for i, (begin, end, phone) in enumerate(self.spans):
            x = int(self.time_x(begin))
            selected = i in [self.selected_boundary, self.hover, self.dragging]
            color = QColor("#ffe0ef" if selected else "#ffb8d9")
            if self.stage == 2:
                color.setAlpha(65)
            p.setPen(QPen(color, 2 if selected and self.stage == 1 else 1, Qt.DashLine))
            p.drawLine(x, int(wave.top()), x, int(spec.bottom()))
        for t, color in zip(
            self.row["absolute"] if self.stage == 2 and self.row else [],
            ["#ffd700", "#22c55e", "#ef4444", "#3b82f6", "#ffffff"],
        ):
            if ui.theme == "light":
                p.setPen(QPen(QColor("#32194c"), 4, Qt.SolidLine))
                p.drawLine(
                    int(self.time_x(t)),
                    int(wave.top()),
                    int(self.time_x(t)),
                    int(spec.bottom()),
                )
            p.setPen(QPen(QColor(color), 2, Qt.SolidLine))
            p.drawLine(
                int(self.time_x(t)),
                int(wave.top()),
                int(self.time_x(t)),
                int(spec.bottom()),
            )
        p.restore()
        for i, (begin, end, phone) in enumerate(self.spans):
            x = max(wave.left(), self.time_x(begin))
            right = min(wave.right(), self.time_x(end))
            if right - x >= 19:
                p.setPen(
                    QColor(
                        ui.colors()["text"] if self.stage == 1 else ui.colors()["muted"]
                    )
                )
                p.drawText(QRectF(x, 2, right - x, 25), Qt.AlignCenter, phone)
        for i in range(6):
            t = self.start + self.length * i / 5
            p.setPen(QColor(ui.colors()["muted"]))
            p.drawText(int(self.time_x(t)) - 18, int(spec.bottom() + 19), f"{t:.2f}s")
        for i, (t, label, color) in enumerate(
            zip(
                self.row["absolute"] if self.stage == 2 and self.row else [],
                ["오프셋", "오버랩", "선행", "고정 끝", "컷오프"],
                ["#ffd700", "#22c55e", "#ef4444", "#3b82f6", "#ffffff"],
            )
        ):
            p.fillRect(
                QRectF(i * self.width() / 5, self.height() - 30, self.width() / 5, 30),
                QColor("#281738"),
            )
            p.setPen(QColor(color))
            p.drawText(
                int(i * self.width() / 5) + 9,
                self.height() - 12,
                f"{self.ordered_markers().index(i)+1} {ui.translate(label)} {t:.3f}s",
            )
