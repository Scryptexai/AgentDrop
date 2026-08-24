"""Action schema: parsing, validation, and execution mapping."""
import pytest

from agentdrop.loop.actions import (
    Action,
    ActionError,
    execute_action,
    parse_action,
)


class RecordingBrowser:
    """Captures the pixel calls execute_action makes."""

    screen_size = (1280, 800)

    def __init__(self):
        self.calls = []

    def click(self, x, y, button="left", click_count=1):
        self.calls.append(("click", x, y, button, click_count))

    def double_click(self, x, y):
        self.calls.append(("double_click", x, y))

    def right_click(self, x, y):
        self.calls.append(("right_click", x, y))

    def drag(self, x1, y1, x2, y2, steps=8):
        self.calls.append(("drag", x1, y1, x2, y2))

    def scroll(self, x, y, dy):
        self.calls.append(("scroll", x, y, dy))

    def type_text(self, text):
        self.calls.append(("type_text", text))

    def press_key(self, key):
        self.calls.append(("press", key))

    def hotkey(self, *keys):
        self.calls.append(("hotkey",) + keys)

    def navigate(self, url):
        self.calls.append(("navigate", url))

    def go_back(self):
        self.calls.append(("back",))

    def go_forward(self):
        self.calls.append(("forward",))

    def reload(self):
        self.calls.append(("reload",))

    def wait(self, seconds):
        self.calls.append(("wait", seconds))


def test_parse_all_action_types():
    cases = {
        "click": {"type": "click", "x": 10, "y": 20},
        "double_click": {"type": "double_click", "x": 10, "y": 20},
        "right_click": {"type": "right_click", "x": 10, "y": 20},
        "drag": {"type": "drag", "x": 0, "y": 0, "x2": 100, "y2": 50},
        "scroll": {"type": "scroll", "direction": "down", "amount": 3},
        "type": {"type": "type", "x": 5, "y": 6, "value": "hi"},
        "press": {"type": "press", "key": "Enter"},
        "hotkey": {"type": "hotkey", "keys": ["ctrl", "c"]},
        "wait": {"type": "wait", "seconds": 1.5},
        "navigate": {"type": "navigate", "url": "https://loqua.example/"},
        "back": {"type": "back"},
        "forward": {"type": "forward"},
        "reload": {"type": "reload"},
        "done": {"type": "done"},
        "error": {"type": "error", "value": "nope"},
    }
    for name, data in cases.items():
        a = parse_action(data, 1280, 800)
        assert a.type == name, name


def test_rejects_out_of_bounds_coordinates():
    with pytest.raises(ActionError):
        parse_action({"type": "click", "x": -5, "y": 10}, 1280, 800)
    with pytest.raises(ActionError):
        parse_action({"type": "click", "x": 10, "y": 801}, 1280, 800)
    with pytest.raises(ActionError):
        parse_action({"type": "click", "x": 1281, "y": 10}, 1280, 800)


def test_rejects_missing_required_fields():
    with pytest.raises(ActionError):
        parse_action({"type": "click", "x": 10}, 1280, 800)
    with pytest.raises(ActionError):
        parse_action({"type": "type", "x": 10, "y": 10}, 1280, 800)  # no value
    with pytest.raises(ActionError):
        parse_action({"type": "drag", "x": 0, "y": 0}, 1280, 800)  # no x2/y2
    with pytest.raises(ActionError):
        parse_action({"type": "hotkey", "keys": ["ctrl"]}, 1280, 800)  # needs 2
    with pytest.raises(ActionError):
        parse_action({"type": "navigate", "url": "javascript:alert(1)"}, 1280, 800)


def test_rejects_unknown_type():
    with pytest.raises(ActionError):
        parse_action({"type": "hover_forever"}, 1280, 800)


def test_accepts_json_string_input():
    a = parse_action('{"type": "click", "x": 1, "y": 2}', 1280, 800)
    assert a.type == "click" and a.x == 1


def test_type_action_focuses_then_types():
    b = RecordingBrowser()
    execute_action(b, parse_action({"type": "type", "x": 40, "y": 50, "value": "abc"}, 1280, 800))
    assert b.calls == [("click", 40, 50, "left", 1), ("type_text", "abc")]


def test_scroll_defaults_to_centre_and_direction():
    b = RecordingBrowser()
    execute_action(b, parse_action({"type": "scroll", "direction": "up", "amount": 2}, 1280, 800))
    assert b.calls == [("scroll", 640, 400, -240)]


def test_click_is_visual_and_done_is_not():
    assert parse_action({"type": "click", "x": 1, "y": 1}, 1280, 800).is_visual
    assert parse_action({"type": "scroll", "direction": "down"}, 1280, 800).is_visual
    assert not parse_action({"type": "wait", "seconds": 1}, 1280, 800).is_visual
    assert not parse_action({"type": "done"}, 1280, 800).is_visual
    assert parse_action({"type": "type", "x": 1, "y": 1, "value": "x"}, 1280, 800).is_soft_visual
