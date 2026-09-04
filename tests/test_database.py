from raspberry_pi_app.database.connection import connect_database
from raspberry_pi_app.database.repository import Repository


def test_sqlite_schema_and_parameterized_packet_insert(config, packet_factory):
    connection = connect_database(":memory:")
    repository = Repository(connection, config.junction["id"])
    packet = packet_factory(distance=80)
    assert repository.record_packet(packet)
    assert not repository.record_packet(packet)
    row = connection.execute("SELECT ambulance_id, condition FROM trips WHERE trip_id=?", (packet.trip_id,)).fetchone()
    assert tuple(row) == (packet.ambulance_id, packet.patient_condition)
    connection.close()
