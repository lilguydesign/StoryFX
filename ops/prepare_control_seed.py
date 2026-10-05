"""Export business settings only; never transport identities, credentials or media."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
from storyfx_server.control_catalog import Catalog
from storyfx_server.control_models import MODELS


def prepare(owner_email, destination):
    folder = ROOT / 'config'
    def source(name, member):
        return json.loads((folder / (name + '.json')).read_text(encoding='utf-8-sig'))[member]
    values = {}
    profiles = source('profiles', 'profiles')
    values['profiles'] = [{'name': name, **{key: profile[key] for key in ('enabled', 'offset_minutes', 'label') if key in profile}}
                          for name, profile in profiles.items()]
    values['systems'] = [{'name': name, 'times': system.get('times', []) if isinstance(system, dict) else system}
                         for name, system in source('systems', 'systems').items()]
    values['albums'] = [{key: album[key] for key in MODELS['albums'].model_fields if key in album}
                        for album in source('albums', 'albums')]
    for value in values['albums']:
        value['count_per_post'] = max(1, int(value.get('count_per_post') or 1))
    values['pages'] = [{key: page[key] for key in ('name', 'country')} for page in source('pages', 'pages')]
    values['matrix'] = [{'name': f"{index + 1:03d} · {row['device']} · {row['system']}",
                        **{key: row[key] for key in MODELS['matrix'].model_fields if key in row}}
                       for index, row in enumerate(source('matrix', 'rows'))]
    values['locators'] = []  # Legacy selectors are code, not a historical JSON catalogue.
    clean = {name: [Catalog.validate(name, value) for value in collection] for name, collection in values.items()}
    receipt = json.loads((ROOT / 'delivery/REAL_WHATSAPP_PUBLICATION_20261005.json').read_text())
    assert receipt['state'] == 'CONFIRMED' and receipt['confirmed_media_count'] == 3
    safe = {key: receipt[key] for key in ('profile', 'system', 'scheduled_at', 'confirmed_media_count', 'provider_evidence', 'confirmed_at')}
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'owner_email': owner_email, 'collections': clean, 'confirmed_publications': [safe]}, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'business_seed_created': True, 'collections': {name: len(value) for name, value in clean.items()},
                      'transport_identifiers_exported': False, 'media_exported': False}))


if __name__ == '__main__':
    prepare(sys.argv[1], sys.argv[2])
