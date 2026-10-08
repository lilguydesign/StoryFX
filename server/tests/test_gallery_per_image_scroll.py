"""Synthetic Gallery interactions: intermediate scrolling and closed failures."""
import unittest
from unittest.mock import patch
import importlib.util
from pathlib import Path
source = Path(__file__).resolve().parents[2] / 'engine/gallery_batch.py'
spec = importlib.util.spec_from_file_location('gallery_batch', source)
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


class Thumb:
    def __init__(self, driver, index):
        self.driver, self.index = driver, index

    def get_attribute(self, key):
        return str(self.index in self.driver.selected).lower() if key == 'checked' else 'false'

    def click(self):
        driver = self.driver
        driver.events.append(('click', self.index))
        if driver.mode == 'stuck':
            return
        if driver.mode == 'decrease':
            driver.selected.pop()
            return
        if self.index in driver.selected:
            driver.selected.remove(self.index)
        else:
            driver.selected.add(self.index)
        if driver.mode == 'uncertain':
            raise TimeoutError('synthetic')


class Gallery:
    def __init__(self, selected=(), mode='normal', total=400, overlapping=False):
        self.selected, self.mode, self.total = set(selected), mode, total
        self.events, self.page, self.overlapping = [], 0, overlapping

    @property
    def page_source(self):
        return (f'<hierarchy><node resource-id="{batch.GALLERY}:id/title" '
                f'text="{len(self.selected)} selected"/></hierarchy>')

    def find_elements(self, by, locator):
        self.events.append(('read', self.page))
        if self.mode == 'empty':
            return []
        start = 0 if self.overlapping else (self.page * 12) % self.total
        return [Thumb(self, i) for i in range(start, min(start + 12, self.total))]

    def get_window_size(self):
        return {'width': 100, 'height': 200}

    def swipe(self, *args):
        self.events.append(('swipe', self.page))
        self.page += 1


def select(driver, count, total=400, maximum=2):
    return batch.select_exact_batch(driver, count, album_total=total, scroll_max=maximum,
                                    pause=lambda _: None, shuffle=lambda _: None)


class PerImageScrollTests(unittest.TestCase):
    def test_large_album_scrolls_between_each_fresh_image_even_when_quota_fits_viewport(self):
        driver = Gallery()
        with patch.object(batch.random, 'randint', return_value=1):
            self.assertEqual(select(driver, 9), 9)
        actions = [kind for kind, _ in driver.events if kind != 'read']
        self.assertEqual(actions, ['click', 'swipe'] * 8 + ['click'])
        self.assertEqual(len(driver.selected), 9)

    def test_no_more_than_configured_scrolls_and_bound_is_unchanged(self):
        for configured, expected in [(0, 1), (1, 1), (4, 4), (99, 10)]:
            with self.subTest(configured=configured):
                driver = Gallery()
                with patch.object(batch.random, 'randint', side_effect=lambda low, high: high) as random:
                    self.assertEqual(select(driver, 3, maximum=configured), 3)
                self.assertEqual(random.call_args_list, [unittest.mock.call(1, expected)] * 2)
                self.assertEqual(sum(kind == 'swipe' for kind, _ in driver.events), 2 * expected)

    def test_initial_selection_and_revisited_checked_items_are_preserved(self):
        driver = Gallery(selected=[0], overlapping=True)
        with patch.object(batch.random, 'randint', return_value=1):
            self.assertEqual(select(driver, 9), 9)
        clicked = [index for kind, index in driver.events if kind == 'click']
        self.assertEqual(len(clicked), 8)
        self.assertEqual(len(set(clicked)), 8)
        self.assertNotIn(0, clicked)
        self.assertIn(0, driver.selected)
        self.assertEqual(driver.events[0][0], 'swipe')
        self.assertEqual(sum(kind == 'swipe' for kind, _ in driver.events), 8)

    def test_scroll_count_change_refuses_before_any_new_click(self):
        driver = Gallery(selected=[0])
        def changed(*args):
            driver.events.append(('swipe', 0))
            driver.selected.clear()
        driver.swipe = changed
        with patch.object(batch.random, 'randint', return_value=1):
            with self.assertRaisesRegex(batch.BatchSelectionError, 'CHANGED_DURING_SCROLL'):
                select(driver, 9)
        self.assertEqual(driver.events, [('swipe', 0)])

    def test_uncertain_scroll_is_never_repeated(self):
        driver = Gallery(selected=[0])
        def uncertain(*args):
            driver.events.append(('swipe', 0))
            raise TimeoutError('synthetic')
        driver.swipe = uncertain
        with self.assertRaisesRegex(batch.BatchSelectionError, 'SCROLL_OUTCOME_UNCERTAIN'):
            select(driver, 9)
        self.assertEqual(driver.events, [('swipe', 0)])

    def test_thirty_images_are_not_truncated_by_former_twelve_page_budget(self):
        driver = Gallery()
        with patch.object(batch.random, 'randint', return_value=1):
            self.assertEqual(select(driver, 30), 30)
        self.assertEqual(sum(kind == 'swipe' for kind, _ in driver.events), 29)

    def test_small_album_behavior_is_preserved_without_scroll(self):
        driver = Gallery(selected=[0], total=12)
        self.assertEqual(select(driver, 9, total=12), 9)
        self.assertFalse(any(kind == 'swipe' for kind, _ in driver.events))

    def test_unknown_size_uses_large_album_path(self):
        driver = Gallery()
        with patch.object(batch.random, 'randint', return_value=1):
            self.assertEqual(select(driver, 3, total=0), 3)
        self.assertEqual(sum(kind == 'swipe' for kind, _ in driver.events), 2)

    def test_exact_initial_count_does_not_click_or_scroll(self):
        driver = Gallery(selected=range(3))
        self.assertEqual(select(driver, 3), 3)
        self.assertEqual(driver.events, [])

    def test_uncertain_click_is_never_repeated(self):
        driver = Gallery(mode='uncertain')
        with self.assertRaisesRegex(batch.BatchSelectionError, 'OUTCOME_UNCERTAIN'):
            select(driver, 9)
        self.assertEqual([event for event in driver.events if event[0] != 'read'], [('click', 0)])
        self.assertEqual(len(driver.selected), 1)

    def test_stuck_or_decreased_count_refuses_before_scroll(self):
        for mode in ['stuck', 'decrease']:
            with self.subTest(mode=mode):
                driver = Gallery(selected=[0], mode=mode)
                with patch.object(batch.random, 'randint', return_value=1), self.assertRaisesRegex(
                        batch.BatchSelectionError, 'DID_NOT_INCREASE'):
                    select(driver, 9)
                self.assertEqual(sum(kind == 'click' for kind, _ in driver.events), 1)
                self.assertEqual(sum(kind == 'swipe' for kind, _ in driver.events), 1)
                self.assertEqual(driver.events[-1][0], 'click')

    def test_empty_pages_stop_at_finite_budget_without_success(self):
        driver = Gallery(mode='empty')
        with patch.object(batch.random, 'randint', return_value=1):
            with self.assertRaisesRegex(batch.BatchSelectionError, 'NOT_CONFIRMED'):
                select(driver, 3)
        self.assertEqual(sum(kind == 'read' for kind, _ in driver.events), 15)

    def test_small_album_never_reduces_request(self):
        driver = Gallery(total=2)
        with self.assertRaisesRegex(batch.BatchSelectionError, 'ALBUM_TOO_SMALL'):
            select(driver, 3, total=2)
        self.assertEqual(driver.events, [])

    def test_count_outside_contract_is_rejected_before_interaction(self):
        for count in [0, 31, True]:
            driver = Gallery()
            with self.assertRaisesRegex(batch.BatchSelectionError, 'COUNT_INVALID'):
                select(driver, count)
            self.assertEqual(driver.events, [])


if __name__ == '__main__':
    unittest.main()
