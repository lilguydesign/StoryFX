import unittest
from storyfx_manual_recipe_install_contract import ANCHOR, CALL, IMPORT, INVOCATION, patch


class ManualRecipeIntegration(unittest.TestCase):
    def source(self):
        return ANCHOR + '\n\ndef collect(now):\n    checks = []\n' + INVOCATION + '\n    return checks\n'

    def test_exact_two_lines_and_idempotence(self):
        original = self.source()
        changed = patch(original)
        self.assertEqual(changed.replace('\n' + IMPORT, '').replace('\n' + CALL, ''), original)
        self.assertEqual(patch(changed), changed)

    def test_partial_duplicate_or_changed_anchor_is_rejected(self):
        for value in (self.source() + IMPORT, self.source().replace(INVOCATION, ''),
                      self.source() + '\n' + ANCHOR, patch(self.source()) + '\n' + IMPORT):
            with self.subTest(value=value), self.assertRaises(ValueError):
                patch(value)


if __name__ == '__main__':
    unittest.main()
