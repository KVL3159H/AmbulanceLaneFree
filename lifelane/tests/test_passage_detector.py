from dataclasses import replace

from raspberry_pi_app.core.gps_engine import GPSEngine
from raspberry_pi_app.core.models import GPSAssessment
from raspberry_pi_app.core.passage_detector import PassageDetector


def test_crossing_requires_entry_and_multiple_increasing_points(config, packet_factory):
    detector = PassageDetector(50, 60)
    engine = GPSEngine(config)
    base = engine.assess(packet_factory(distance=30, sequence=1))
    assert not detector.update(base)
    # Southbound vehicle is now beyond the centre: bearing to centre is north (0), heading is south (180).
    for sequence, distance in [(2, 10), (3, 18)]:
        packet = packet_factory(distance=-distance, sequence=sequence)
        result = engine.assess(packet)
        assert not detector.update(result)
    packet = packet_factory(distance=-30, sequence=4)
    assert detector.update(engine.assess(packet))


def test_single_point_cannot_restore_normal(config, packet_factory):
    detector = PassageDetector(50)
    assessment = GPSEngine(config).assess(packet_factory(distance=10))
    assert not detector.update(assessment)
