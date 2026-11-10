"""Tap sounds. Each sound is a prerolled GStreamer pipeline, so a tap only
needs a flushing seek back to the start, which keeps latency low."""
import gi

gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst  # noqa: E402

from . import styles  # noqa: E402

Gst.init(None)


class _Clip:
    def __init__(self, path):
        self.pipeline = Gst.ElementFactory.make("playbin", None)
        self.ok = self.pipeline is not None and path.exists()
        if not self.ok:
            return
        self.pipeline.set_property("uri", GLib.filename_to_uri(str(path), None))
        fakevideo = Gst.ElementFactory.make("fakesink", None)
        if fakevideo:
            self.pipeline.set_property("video-sink", fakevideo)
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::eos", self._eos)
        bus.connect("message::error", self._error)
        self.warm = False

    def preroll(self):
        if self.ok and not self.warm:
            self.pipeline.set_state(Gst.State.PAUSED)
            self.warm = True

    def play(self):
        if not self.ok:
            return
        self.preroll()
        self.pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE, 0)
        self.pipeline.set_state(Gst.State.PLAYING)

    def stop(self):
        if self.ok:
            self.pipeline.set_state(Gst.State.NULL)
            self.warm = False

    def _eos(self, *_):
        self.pipeline.set_state(Gst.State.PAUSED)

    def _error(self, _bus, msg):
        err, _ = msg.parse_error()
        print("tinyhand: sound error:", err.message)
        self.ok = False


class TapSound:
    def __init__(self, choice="thock"):
        self.enabled = True
        self._clips = {}
        self.choice = choice
        self._idle = None

    def _clip(self, choice):
        if choice not in self._clips:
            self._clips[choice] = _Clip(styles.sound_path(choice))
        return self._clips[choice]

    def load(self, choice):
        self.choice = choice

    def warm(self):
        self._clip(self.choice).preroll()
        self._arm_idle()

    def play(self, force=False):
        if not (self.enabled or force):
            return
        self._clip(self.choice).play()
        self._arm_idle()

    def preview(self, choice):
        self._clip(choice).play()
        self._arm_idle()

    def _arm_idle(self):
        # Release the audio device after 30 s of quiet, like the macOS app.
        if self._idle:
            GLib.source_remove(self._idle)
        self._idle = GLib.timeout_add_seconds(30, self._sleep)

    def _sleep(self):
        self._idle = None
        for c in self._clips.values():
            c.stop()
        return False
