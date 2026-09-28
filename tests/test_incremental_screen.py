from concurrent.futures import ThreadPoolExecutor

from PIL import Image

from screen_transport import IncrementalFrameSender, TuringScreenTransport


def test_partial_transport_sends_only_a_changed_pixel(monkeypatch):
    writes = []

    class Device:
        def write(self, payload):
            writes.append(bytes(payload))
            return len(payload)

        def flush(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    import sys
    import types

    serial = types.ModuleType("serial")
    serial.Serial = lambda *args, **kwargs: Device()
    monkeypatch.setitem(sys.modules, "serial", serial)

    previous = Image.new("RGB", (320, 480), "#000000")
    current = previous.copy()
    current.putpixel((4, 2), (255, 0, 0))
    changed = TuringScreenTransport("FAKE1").send_changed_image(current, previous)

    assert changed == 1
    assert writes[0][5:11] == bytes((121, 100, 1, 64, 1, 224))
    assert writes[1] == TuringScreenTransport._command(4, 2, 4, 2, 197)
    assert len(writes[2]) == 2


def test_unchanged_frame_does_not_open_a_serial_port(monkeypatch):
    import sys
    import types

    serial = types.ModuleType("serial")
    serial.Serial = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected serial open"))
    monkeypatch.setitem(sys.modules, "serial", serial)
    image = Image.new("RGB", (320, 480), "#222222")

    assert TuringScreenTransport("FAKE1").send_changed_image(image, image.copy()) == 0


def test_sender_full_syncs_first_then_uses_deltas_and_backoff_after_failure():
    now = [0.0]

    class FakeTransport:
        def __init__(self):
            self.full = []
            self.deltas = []
            self.fail_delta = False

        def send_pil_image(self, image):
            self.full.append(image.copy())

        def send_changed_image(self, image, previous):
            if self.fail_delta:
                raise OSError("disconnected")
            self.deltas.append((image.copy(), previous.copy()))
            return 1

    transport = FakeTransport()
    sender = IncrementalFrameSender("FAKE1", transport=transport, clock=lambda: now[0], full_refresh_interval=300)
    first = Image.new("RGB", (320, 480), "#000000")
    second = first.copy()
    second.putpixel((1, 1), (255, 0, 0))

    assert sender.send_frame(first).full_refresh is True
    assert sender.send_frame(second).full_refresh is False
    assert len(transport.full) == 1
    assert len(transport.deltas) == 1

    transport.fail_delta = True
    third = second.copy()
    third.putpixel((2, 2), (0, 255, 0))
    try:
        sender.send_frame(third)
    except OSError:
        pass
    else:
        raise AssertionError("expected transport failure")

    assert sender.can_send(now[0]) is False
    now[0] += 5.0
    assert sender.can_send(now[0]) is True
    transport.fail_delta = False
    assert sender.send_frame(third).full_refresh is True


def test_sender_resynchronizes_after_the_configured_full_refresh_interval():
    now = [0.0]

    class FakeTransport:
        def __init__(self):
            self.full = 0

        def send_pil_image(self, _image):
            self.full += 1

        def send_changed_image(self, _image, _previous):
            return 0

    transport = FakeTransport()
    sender = IncrementalFrameSender("FAKE1", transport=transport, clock=lambda: now[0], full_refresh_interval=60)
    image = Image.new("RGB", (320, 480), "#000000")
    sender.send_frame(image)
    now[0] = 60
    assert sender.send_frame(image).full_refresh is True
    assert transport.full == 2