"""Actual counts, toggle regressions and batch truncation before provider handoff."""
import importlib.util
from pathlib import Path
import pytest

path = Path(__file__).resolve().parents[2] / 'engine/gallery_batch.py'
spec = importlib.util.spec_from_file_location('gallery_batch', path)
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


def xml(count, package=batch.GALLERY):
    return f'<hierarchy><node package="{package}" resource-id="{package}:id/title" text="{count} selected"/></hierarchy>'


class Thumb:
    def __init__(self, driver, index):
        self.driver, self.index = driver, index

    def get_attribute(self, key):
        return str(self.index in self.driver.selected).lower() if key == 'selected' else 'false'

    def click(self):
        self.driver.clicks += 1
        if self.driver.stuck:
            return
        if self.index in self.driver.selected:
            self.driver.selected.remove(self.index)
        else:
            self.driver.selected.add(self.index)


class Gallery:
    def __init__(self, selected=(), size=12, stuck=False):
        self.selected, self.size, self.stuck = set(selected), size, stuck
        self.clicks = 0

    @property
    def page_source(self):
        return xml(len(self.selected))

    def find_elements(self, by, locator):
        return [Thumb(self, i) for i in range(self.size)]


def select(driver, count, **kwargs):
    return batch.select_exact_batch(driver, count, album_total=driver.size,
                                    pause=lambda _: None, shuffle=lambda _: None, **kwargs)


@pytest.mark.parametrize('count', [3, 5, 9, 11])
def test_keeps_already_selected_first_thumb_and_reaches_exact_batch(count):
    driver = Gallery(selected=[0])
    assert select(driver, count) == count
    assert driver.clicks == count - 1
    assert 0 in driver.selected and len(driver.selected) == count


def test_refuses_a_click_without_actual_selection_change():
    driver = Gallery(stuck=True)
    with pytest.raises(batch.BatchSelectionError, match='DID_NOT_INCREASE'):
        select(driver, 9)
    assert driver.clicks == 1


def test_revisited_selected_thumbnail_is_never_toggled_off():
    driver = Gallery(selected=[0, 1, 2])
    assert select(driver, 5) == 5
    assert driver.clicks == 2 and {0, 1, 2} <= driver.selected


def test_small_album_never_silently_reduces_the_requested_count():
    driver = Gallery(size=3)
    with pytest.raises(batch.BatchSelectionError, match='ALBUM_TOO_SMALL'):
        select(driver, 11)
    assert driver.clicks == 0


def test_ambiguous_missing_or_external_counter_is_not_proof():
    for source in ('<hierarchy/>', xml(3, 'other.app'), xml(3).replace('</hierarchy>',
                   f'<node resource-id="{batch.GALLERY}:id/count" text="4 selected"/></hierarchy>')):
        with pytest.raises(batch.BatchSelectionError, match='COUNT_UNAVAILABLE'):
            batch.selection_count(source)


@pytest.mark.parametrize('label', ['9 selected', '9 images sélectionnées', 'Sélectionnés : 9'])
def test_supported_counter_languages(label):
    assert batch.selection_count(xml(9).replace('9 selected', label)) == 9


def test_android_handoff_refuses_one_image_when_nine_were_selected():
    class Chooser:
        page_source = '<hierarchy><node package="com.android.intentresolver" text="1 image"/></hierarchy>'
    with pytest.raises(batch.BatchSelectionError, match='COUNT_MISMATCH'):
        batch.verify_shared_batch(Chooser(), 9)
    Chooser.page_source = Chooser.page_source.replace('1 image', '9 images')
    batch.verify_shared_batch(Chooser(), 9)


def test_whatsapp_one_selected_recipient_is_not_a_media_batch_counter():
    with pytest.raises(batch.BatchSelectionError):
        batch.shared_count('<hierarchy><node package="com.whatsapp.w4b" text="1 selected"/></hierarchy>')
