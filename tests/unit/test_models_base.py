from contracting_hub.models import AppModel, TimestampedModel, utc_now


def test_timestamped_model_includes_primary_key_and_timestamps() -> None:
    class ExampleRecord(TimestampedModel, table=False):
        pass

    assert issubclass(ExampleRecord, AppModel)
    assert "id" in ExampleRecord.model_fields
    assert ExampleRecord.model_fields["created_at"].default_factory is utc_now
    assert ExampleRecord.model_fields["updated_at"].default_factory is utc_now
