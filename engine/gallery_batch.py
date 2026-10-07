"""Count actual Gallery selections; a click is never proof of a selected image."""
import random
import re
import time
from xml.etree import ElementTree

GALLERY = 'com.sec.android.gallery3d'
THUMBNAILS = f"//android.widget.FrameLayout[@resource-id='{GALLERY}:id/thumbnail_preview_layout']"
SELECTED = re.compile(r'(?:(\d+) (?:items? |images? |photos? )?(?:selected|sélectionné(?:e)?s?)|'
                      r'(?:selected|sélectionné(?:e)?s?)\s*:?\s*(\d+))', re.IGNORECASE)
EMPTY = {'select items', 'select item', 'sélectionner des éléments', 'sélectionner les éléments'}


class BatchSelectionError(RuntimeError):
    """Closed failure: no provider send is allowed after this error."""


def selection_count(source):
    root = ElementTree.fromstring(source)
    values = set()
    for node in root.iter('node'):
        if not node.get('resource-id', '').startswith(GALLERY + ':'):
            continue
        for field in ('text', 'content-desc'):
            label = node.get(field, '').strip()
            match = SELECTED.fullmatch(label)
            if match:
                values.add(int(next(value for value in match.groups() if value is not None)))
            elif label.casefold() in EMPTY:
                values.add(0)
    if len(values) != 1:
        raise BatchSelectionError('GALLERY_SELECTION_COUNT_UNAVAILABLE')
    return values.pop()


def shared_count(source):
    """Android's chooser must acknowledge the full batch before choosing an app."""
    root = ElementTree.fromstring(source)
    values = set()
    for node in root.iter('node'):
        if node.get('package') not in {'android', 'com.android.intentresolver', 'com.android.systemui'}:
            continue
        for field in ('text', 'content-desc'):
            match = re.fullmatch(r'(\d+) (?:images?|photos?|items?|éléments?)',
                                 node.get(field, '').strip(), re.IGNORECASE)
            if match:
                values.add(int(match[1]))
    if len(values) != 1:
        raise BatchSelectionError('SHARED_BATCH_COUNT_UNAVAILABLE')
    return values.pop()


def verify_shared_batch(driver, requested):
    if shared_count(driver.page_source) != requested:
        raise BatchSelectionError('SHARED_BATCH_COUNT_MISMATCH')


def select_exact_batch(driver, requested, *, album_total=0, scroll_max=3,
                       pause=time.sleep, shuffle=random.shuffle):
    if type(requested) is not int or not 1 <= requested <= 30:
        raise BatchSelectionError('BATCH_COUNT_INVALID')
    if album_total and album_total < requested:
        raise BatchSelectionError('ALBUM_TOO_SMALL_FOR_REQUESTED_BATCH')
    actual = selection_count(driver.page_source)
    if actual > requested:
        raise BatchSelectionError('INITIAL_SELECTION_EXCEEDS_REQUEST')
    for _ in range(12):
        if actual == requested:
            break
        thumbs = list(driver.find_elements('xpath', THUMBNAILS))
        shuffle(thumbs)
        for thumb in thumbs:
            if actual == requested:
                break
            if any(str(thumb.get_attribute(key)).lower() == 'true' for key in ('selected', 'checked')):
                continue
            # An uncertain click is never repeated. Its outcome may already have changed selection.
            try:
                thumb.click()
            except Exception:
                raise BatchSelectionError('GALLERY_CLICK_OUTCOME_UNCERTAIN') from None
            pause(.25)
            after = selection_count(driver.page_source)
            if after != actual + 1:
                raise BatchSelectionError('GALLERY_SELECTION_DID_NOT_INCREASE')
            actual = after
        if actual == requested or album_total and album_total <= 32:
            break
        size = driver.get_window_size()
        for _ in range(random.randint(1, max(1, min(10, scroll_max)))):
            driver.swipe(size['width'] // 2, int(size['height'] * .75),
                         size['width'] // 2, int(size['height'] * .25), 900)
            pause(.4)
    if actual != requested or selection_count(driver.page_source) != requested:
        raise BatchSelectionError('EXACT_BATCH_SELECTION_NOT_CONFIRMED')
    return actual
