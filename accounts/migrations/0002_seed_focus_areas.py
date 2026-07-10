from django.db import migrations

FOCUS_AREAS = ["Frontend", "Backend", "Data", "DevOps", "Mobile"]


def seed_focus_areas(apps, schema_editor):
    FocusArea = apps.get_model("accounts", "FocusArea")
    for name in FOCUS_AREAS:
        FocusArea.objects.get_or_create(name=name)


def unseed_focus_areas(apps, schema_editor):
    FocusArea = apps.get_model("accounts", "FocusArea")
    FocusArea.objects.filter(name__in=FOCUS_AREAS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_focus_areas, unseed_focus_areas),
    ]
