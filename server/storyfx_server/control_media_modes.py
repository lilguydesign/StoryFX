"""Shared WhatsApp media limits; new modes require an explicit capable agent."""
MODES = {'intro', 'multi', 'intro+multi'}


def media_count(value):
    return 1 if value['engine'] == 'intro' else value['count'] + (value['engine'] == 'intro+multi')


def supported_media(value):
    count = value.get('count')
    return (value.get('enabled', True) and value.get('platform') == 'WhatsApp'
            and value.get('engine') in MODES and type(count) is int and 1 <= count <= 30
            and media_count(value) <= 30 and not value.get('page') and not value.get('page_name')
            and bool(value.get('album') if value['engine'] == 'intro' else value.get('album2') or value.get('album'))
            and (value['engine'] != 'intro+multi' or bool(value.get('album'))))


def requires_media_v2(value):
    return value.get('engine') != 'multi' or 'video' in ''.join(
        value.get(key) or '' for key in ('system', 'album', 'album2')).casefold()


def capable_version(version):
    return tuple(map(int, version.split('.'))) >= (0, 4, 13)
