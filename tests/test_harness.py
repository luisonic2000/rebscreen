from dataclasses import dataclass


@dataclass
class FakeTransport:
    frames: list[object]
    def send_pil_image(self, image):
        self.frames.append(image)


def test_screen_dry_run_never_uses_com3():
    transport = FakeTransport([])
    frame = object()
    transport.send_pil_image(frame)
    assert transport.frames == [frame]
