import app
import screen_transport


def test_app_reexports_the_usb_transport_from_its_dedicated_module():
    assert app.TuringScreenTransport is screen_transport.TuringScreenTransport
    assert app._send_frame_to_display is screen_transport.send_frame_to_display
