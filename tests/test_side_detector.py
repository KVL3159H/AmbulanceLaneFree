import pytest

from raspberry_pi_app.core.models import Approach
from raspberry_pi_app.core.side_detector import detect_approach


@pytest.mark.parametrize(
    ("bearing", "expected"),
    [(0, Approach.NORTH), (180, Approach.SOUTH), (90, Approach.EAST), (270, Approach.WEST)],
)
def test_cardinal_side_detection(bearing, expected):
    assert detect_approach(bearing) is expected


def test_bearing_wrap_around_near_zero():
    assert detect_approach(359.9) is Approach.NORTH
    assert detect_approach(0.1) is Approach.NORTH
