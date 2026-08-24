"""Screenshot change detection: the loop's honesty mechanism."""
import io

from PIL import Image, ImageDraw

from agentdrop.vision import verify
from fakesites.loqua.site import FakeLoquaSite


def _png(draw_fn) -> bytes:
    img = Image.new("RGB", (1280, 800), (17, 24, 39))
    draw_fn(ImageDraw.Draw(img))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_identical_screenshots_not_changed():
    site = FakeLoquaSite()
    a = site.screenshot()
    b = site.screenshot()
    assert verify.diff_ratio(a, b) == 0.0
    assert not verify.images_changed(a, b)
    assert verify.is_near_identical(a, b)


def test_navigation_change_detected():
    site = FakeLoquaSite()
    before = site.screenshot()
    site.click(640, 432)  # Get Started -> register
    after = site.screenshot()
    assert verify.images_changed(before, after)


def test_small_text_change_detected():
    """Typing a few characters is a small local change — must be caught
    even though the mean diff stays below a naive global threshold."""
    site = FakeLoquaSite()
    site.click(640, 432)  # -> register
    before = site.screenshot()
    site.click(400, 292)  # focus email
    site.type_text("agent@drop.test")
    after = site.screenshot()
    assert verify.diff_ratio(before, after) < 1.0  # small by mean...
    assert verify.images_changed(before, after)     # ...but still a change


def test_button_move_detected_and_hash_flips():
    site = FakeLoquaSite()
    site.arm_ui_change(after_steps=1, shift=150)
    before = site.screenshot()
    site.click(640, 432)  # triggers the mutation + navigation
    after = site.screenshot()
    assert verify.images_changed(before, after)
    assert verify.image_hash(before) != verify.image_hash(after)


def test_hash_stable_for_same_render():
    site = FakeLoquaSite()
    assert verify.image_hash(site.screenshot()) == verify.image_hash(site.screenshot())
