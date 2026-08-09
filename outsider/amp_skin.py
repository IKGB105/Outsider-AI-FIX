'''Photo-realistic skin for the Blackstar ID:15 TVP front panel.

Overlays small rotating-knob widgets on top of a photo of the real amp
panel, positioned at each physical knob's location. Each dial only
mirrors the corresponding classic QSlider/QComboBox/QRadioButton that
already exists in outsider.ui and already drives all the real amp
communication (see outsider.py's on_<name>_* handlers) - this widget
never talks to the amp directly.

Coordinates are measured against the panel photo in the native
1200x211 image's pixel space (by rendering a debug overlay and
comparing against crops of the photo, not guessed blind); nudge the
tables below if a dial/LED ends up a few pixels off its printed knob.
'''
import os

from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QCheckBox, QDial, QLabel, QPushButton, QWidget

_NATIVE_WIDTH = 1200
_NATIVE_HEIGHT = 211

# (slider object name, knob center x, knob center y, knob diameter)
#
# masterVolumeSlider is deliberately left out: the classic UI keeps
# masterGroupBox permanently disabled (see Ui.controls_enabled -
# "master controls (always disabled)"), i.e. the app already treats
# master volume as read-only from software, never sent to the amp. A
# skin dial for it would just be a knob you can turn that does nothing.
_KNOBS = [
    ('gainSlider', 270, 78, 76),
    ('volumeSlider', 348, 78, 76),
    ('bassSlider', 437, 82, 76),
    ('trebleSlider', 516, 82, 76),
    ('isfSlider', 595, 82, 76),
]

# (combo box object name, knob center x, knob center y, knob diameter)
# Voice and TVP are 6-position rotary selectors, not continuous 0-10
# knobs - same _RotaryDial widget works fine for this (it only cares
# about min/max/value), just wired to a QComboBox's index instead of a
# QSlider's value.
_SELECTORS = [
    ('voiceComboBox', 180, 80, 78),
    ('TVPComboBox', 718, 80, 78),
]

# Position-indicator LEDs around Voice/TVP, one per combo box index (see
# outsider.ui for the item order these line up with) - only the one at
# the current index lights up, like the real amp.
_VOICE_LEDS = [
    (169.5, 125),    # 0 Clean Warm
    (147.5, 111.25), # 1 Clean Bright
    (137.5, 90.5),   # 2 Crunch
    (138.25, 68),    # 3 Super Crunch
    (150, 47),       # 4 OD1
    (169.5, 33),     # 5 OD2
]
_TVP_LEDS = [
    (705.6, 125.6),  # 0 EL84
    (685, 113.4),    # 1 6V6
    (674, 92),       # 2 EL34
    (673.6, 68),     # 3 KT66
    (684.4, 46.4),   # 4 6L6
    (705, 34),       # 5 KT88
]
_SELECTOR_LEDS = {
    'voiceComboBox': _VOICE_LEDS,
    'TVPComboBox': _TVP_LEDS,
}

# (radio button object name, LED center x, LED center y, LED diameter)
# Mod/Delay/Reverb are each independent on/off effect switches (not a
# mutually-exclusive selector), so these mirror on/off state only - no
# button group needed here, same as the real radio buttons.
_LEDS = [
    ('modRadioButton', 803, 42, 16),
    ('delayRadioButton', 803, 81, 16),
    ('reverbRadioButton', 803, 120, 16),
    # The real amp's bottom-row "TVP" footswitch button, not the little
    # ring of valve-type LEDs next to the TVP knob (those are handled by
    # _TVP_LEDS/_SelectorLed instead, for which valve is selected - this
    # is the separate on/off switch for TVP mode itself).
    ('TVPRadioButton', 718, 176, 15),
]


class _RotaryDial(QDial):
    '''A knob that actually turns. The photo's own knob is a black
    cylinder with a printed indicator line - photographed at some fixed,
    arbitrary angle. Real knob bodies look the same at any rotation
    (it's a plain cylinder), so instead of trying to rotate a raster
    crop of the photo (blurry, and the crop edge would show), this
    paints a same-colour cap slightly smaller than the printed knob
    (masking its static line) and draws a fresh indicator line rotated
    to the current value on top - the bezel/ring from the photo stays
    visible around the edge, only the cap+line are ours.

    Dragging uses a plain vertical-distance-to-value mapping (like a
    mixing-console fader turned into a knob), not QDial's built-in
    angle-from-centre grab - angle-based dragging is very sensitive on a
    small widget (a tiny mouse move near the centre swings the angle
    wildly), which is what "turns too much" was about.'''

    SWEEP_DEG = 300  # measured off the photo's own 0/10 tick marks
    CAP_COLOR = QColor(24, 24, 24)
    LINE_COLOR = QColor(230, 230, 230)
    PIXELS_FOR_FULL_SWEEP = 150

    def __init__(self, parent=None, sweep_deg=None, center_deg=0):
        super(_RotaryDial, self).__init__(parent)
        self._drag_start_y = None
        self._drag_start_value = None
        # Real rotary selectors (Voice/TVP) only physically travel
        # through about half the arc a continuous 0-10 knob does, even
        # though they still land on the same 6 positions - lets callers
        # override the class default for just those.
        self.sweep_deg = sweep_deg if sweep_deg is not None else self.SWEEP_DEG
        # Which direction the middle of the sweep points (0 = straight
        # up, -90 = left) - Voice/TVP's label arc sits entirely to the
        # knob's left, not centred on top.
        self.center_deg = center_deg

    def mousePressEvent(self, event):
        self._drag_start_y = event.pos().y()
        self._drag_start_value = self.value()

    def mouseMoveEvent(self, event):
        if self._drag_start_y is None:
            return
        span = self.maximum() - self.minimum()
        delta_px = self._drag_start_y - event.pos().y()  # up = increase
        delta_value = delta_px / self.PIXELS_FOR_FULL_SWEEP * span
        self.setValue(int(round(self._drag_start_value + delta_value)))

    def mouseReleaseEvent(self, event):
        self._drag_start_y = None
        self._drag_start_value = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        side = min(self.width(), self.height())
        cap_d = side * 0.86
        center = QPointF(self.width() / 2.0, self.height() / 2.0)

        painter.setPen(Qt.NoPen)
        painter.setBrush(self.CAP_COLOR)
        painter.drawEllipse(center, cap_d / 2, cap_d / 2)

        span = self.maximum() - self.minimum()
        fraction = 0.0 if span == 0 else (self.value() - self.minimum()) / span
        angle = self.center_deg - self.sweep_deg / 2 + fraction * self.sweep_deg

        painter.translate(center)
        painter.rotate(angle)
        pen = QPen(self.LINE_COLOR)
        pen.setWidth(max(2, int(side * 0.045)))
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(0, -int(cap_d * 0.42), 0, -int(cap_d * 0.14))


class _LedButton(QPushButton):
    '''A checkable "LED" - red when off, green when on.'''

    OFF_COLOR = QColor(150, 20, 20)
    ON_COLOR = QColor(40, 200, 70)

    def __init__(self, parent=None):
        super(_LedButton, self).__init__(parent)
        self.setCheckable(True)
        self.setStyleSheet('background: transparent; border: none;')
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.ON_COLOR if self.isChecked() else self.OFF_COLOR)
        r = min(self.width(), self.height()) / 2.0
        painter.drawEllipse(QPointF(self.width() / 2.0, self.height() / 2.0), r, r)


class _SelectorLed(QWidget):
    '''A dot that jumps between fixed spots (Voice/TVP's ring of printed
    position labels) to match a combo box's current index - only one lit
    at a time, like the real amp. Spans the whole panel (like the photo
    itself) since its lit position moves around; transparent everywhere
    else and never intercepts the mouse, so it can't block the dial
    underneath.'''

    COLOR = QColor(220, 30, 30)
    DOT_D = 11

    def __init__(self, positions, scale, size, parent=None):
        super(_SelectorLed, self).__init__(parent)
        self._positions = positions
        self._scale = scale
        self._index = 0
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFixedSize(*size)

    def setIndex(self, index):
        if 0 <= index < len(self._positions):
            self._index = index
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.COLOR)
        x, y = self._positions[self._index]
        r = self.DOT_D / 2
        painter.drawEllipse(QPointF(x * self._scale, y * self._scale), r, r)


class AmpSkinPanel(QWidget):
    '''sliders/selectors/radios: dicts mapping the names in _KNOBS/
    _SELECTORS/_LEDS to the real QSlider/QComboBox/QRadioButton widgets -
    all already created by uic.loadUi from outsider.ui.'''

    SCALE = 1.6
    _BOTTOM_BAR_HEIGHT = 28

    def __init__(self, sliders, selectors, radios, parent=None):
        super(AmpSkinPanel, self).__init__(parent)

        image_path = os.path.join(os.path.split(__file__)[0], 'skin', 'id15tvp.jpg')
        pixmap = QPixmap(image_path)

        width = int(_NATIVE_WIDTH * self.SCALE)
        photo_height = int(_NATIVE_HEIGHT * self.SCALE)

        photo = QLabel(self)
        photo.setPixmap(pixmap.scaled(width, photo_height, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        photo.setGeometry(0, 0, width, photo_height)

        self.setFixedSize(width, photo_height + self._BOTTOM_BAR_HEIGHT)

        self.dials = {}
        self.valueLabels = {}
        for name, x, y, diameter in _KNOBS:
            slider = sliders[name]

            dial = _RotaryDial(self)
            dial.setMinimum(slider.minimum())
            dial.setMaximum(slider.maximum())
            dial.setValue(slider.value())
            dial.setStyleSheet('background: transparent; border: none;')
            dial.setCursor(Qt.PointingHandCursor)
            dial.setToolTip(name[:-len('Slider')])

            geom_d = int(diameter * self.SCALE)
            geom_x = int(x * self.SCALE - geom_d / 2)
            geom_y = int(y * self.SCALE - geom_d / 2)
            dial.setGeometry(geom_x, geom_y, geom_d, geom_d)

            # Two-way mirror with the classic slider - QSlider/QDial only
            # emit valueChanged when the value actually changes, so this
            # can't loop back on itself.
            dial.valueChanged.connect(slider.setValue)
            slider.valueChanged.connect(dial.setValue)

            self.dials[name] = dial

            # Small "0-10" readout under the knob, matching the photo's
            # own printed scale (the real value is 0-127 internally -
            # see gainLcdNumber etc. in the classic UI for that raw
            # number; this is a friendlier one to read at a glance here).
            label = QLabel(self)
            label.setAlignment(Qt.AlignHCenter)
            label.setStyleSheet('color: rgb(210,210,210); background: transparent; font-size: 13px; font-weight: bold;')
            label_w = int(50 * self.SCALE)
            label.setGeometry(int(x * self.SCALE - label_w / 2), geom_y + geom_d + 2, label_w, 14)

            def _update_label(value, slider=slider, label=label):
                span = slider.maximum() - slider.minimum() or 1
                label.setText(str(round((value - slider.minimum()) / span * 10)))

            dial.valueChanged.connect(_update_label)
            _update_label(dial.value())
            self.valueLabels[name] = label

        for name, x, y, diameter in _SELECTORS:
            combo = selectors[name]

            dial = _RotaryDial(self, sweep_deg=_RotaryDial.SWEEP_DEG / 2, center_deg=-90)
            dial.setMinimum(0)
            dial.setMaximum(max(combo.count() - 1, 0))
            dial.setValue(combo.currentIndex())
            dial.setStyleSheet('background: transparent; border: none;')
            dial.setCursor(Qt.PointingHandCursor)
            dial.setToolTip(name[:-len('ComboBox')])

            geom_d = int(diameter * self.SCALE)
            geom_x = int(x * self.SCALE - geom_d / 2)
            geom_y = int(y * self.SCALE - geom_d / 2)
            dial.setGeometry(geom_x, geom_y, geom_d, geom_d)

            # Same two-way mirror pattern as the slider-backed knobs,
            # just against currentIndex instead of value.
            dial.valueChanged.connect(combo.setCurrentIndex)
            combo.currentIndexChanged.connect(dial.setValue)

            self.dials[name] = dial

            # Created after `photo`, so it already paints on top of it by
            # default Z-order - no explicit raise/lower needed.
            led = _SelectorLed(_SELECTOR_LEDS[name], self.SCALE, (width, photo_height), self)
            led.move(0, 0)
            led.setIndex(dial.value())
            dial.valueChanged.connect(led.setIndex)

        self.leds = {}
        for name, x, y, diameter in _LEDS:
            radio = radios[name]

            led = _LedButton(self)
            led.setChecked(radio.isChecked())
            led.setToolTip(name[:-len('RadioButton')])

            geom_d = int(diameter * self.SCALE)
            geom_x = int(x * self.SCALE - geom_d / 2)
            geom_y = int(y * self.SCALE - geom_d / 2)
            led.setGeometry(geom_x, geom_y, geom_d, geom_d)

            # Same two-way mirror pattern as the dials above.
            led.toggled.connect(radio.setChecked)
            radio.toggled.connect(led.setChecked)

            self.leds[name] = led

        self.hideDuplicatesCheckbox = QCheckBox('Hide duplicate controls below', self)
        self.hideDuplicatesCheckbox.setGeometry(8, photo_height + 4, width - 16, self._BOTTOM_BAR_HEIGHT - 8)

    def sync_from_amp(self, name, value):
        '''Called alongside the classic slider's own blockSignals-guarded
        update (see outsider.py's *_changed_on_amp handlers), since that
        guard also suppresses the slider->dial mirror connection above.'''
        dial = self.dials.get(name)
        if dial is not None:
            dial.setValue(value)
