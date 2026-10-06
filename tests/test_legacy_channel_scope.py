"""The legacy planner obeys per-row channel disabling without touching a profile."""
from legacy_scheduler_plan import iter_jobs


def test_disabled_channel_preserves_other_channel_and_offset():
    profiles = {'profiles': {'Validation technique': {'enabled': True, 'offset_minutes': 15}}}
    systems = {'systems': {'Validation technique': ['06:00']}}
    row = {'device': 'Validation technique', 'system': 'Validation technique', 'engine': 'multi',
           'album2': 'Validation technique', 'count': 3}
    matrix = {'rows': [{**row, 'platform': 'WhatsApp', 'enabled': False},
                       {**row, 'platform': 'Facebook', 'page_name': 'Validation technique'}]}
    jobs = list(iter_jobs(profiles, systems, matrix, {'albums': []}))
    assert len(jobs) == 1
    assert jobs[0]['platform'] == 'Facebook'
    assert jobs[0]['time_effective'] == '06:15'
