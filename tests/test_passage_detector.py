from datetime import datetime, timedelta, timezone
from raspberry_pi_app.core.gps_engine import GPSEngine
from raspberry_pi_app.core.passage_detector import PassageDetector


def test_crossing_requires_entry_and_three_points_beyond_exit(config, packet_factory):
    detector = PassageDetector(80, 60)
    engine = GPSEngine(config)
    now = datetime.now(timezone.utc)
    distances = [100,90,80,70,30,10,-5,-15,-30,-60,-105,-115,-125]
    for i, distance in enumerate(distances):
        stamp = now+timedelta(seconds=i)
        assessment = engine.assess(packet_factory(distance=distance, sequence=i+1, timestamp=stamp), stamp)
        assert assessment.valid
        crossed = detector.update(assessment)
        assert crossed == (i == len(distances)-1)


def test_single_point_cannot_restore_normal(config, packet_factory):
    detector = PassageDetector(80)
    assessment = GPSEngine(config).assess(packet_factory(distance=10))
    assert not detector.update(assessment)
    assert not detector.entered_zone(assessment.packet.trip_id)
