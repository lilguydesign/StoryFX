import unittest
from storyfx_publication_install_contract import patch, IMPORT, CALL


class PublicationIntegration(unittest.TestCase):
    def source(self):
        return ('from storyfx_public_probe import collect_storyfx_public_checks\n'
                'def collect(now):\n    checks = []\n'
                '    checks.extend(collect_storyfx_public_checks(now=now))\n'
                '    return checks\n')

    def test_adds_only_two_lines_and_is_idempotent(self):
        source = self.source()
        patched = patch(source)
        self.assertEqual(patch(patched), patched)
        self.assertEqual(patched.replace('\n' + IMPORT, '').replace('\n' + CALL, ''), source)

    def test_partial_or_changed_target_fails_closed(self):
        for value in (self.source() + IMPORT, self.source().replace('checks.extend', 'checks.append'), ''):
            with self.subTest(value=value), self.assertRaises(ValueError):
                patch(value)


if __name__ == '__main__':
    unittest.main()
