import hashlib
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import footage_director as footage


class LocalVideoCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / 'footage.sqlite3'
        self.cache = self.root / 'provider-cache'
        self.local = self.root / 'local-video-cache'
        self.patches = [
            patch.object(footage, 'DB', self.db),
            patch.object(footage, 'CACHE', self.cache),
            patch.object(footage, 'LOCAL_CACHE', self.local),
            patch.object(footage, 'MAX_LOCAL_CACHE_GB', 50),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def test_cache_copy_is_registered_and_retrievable(self):
        source = self.root / 'validated.mp4'
        source.write_bytes(b'validated video fixture')

        cached = footage.download_video(source, 'pexels-101')

        self.assertEqual(cached.read_bytes(), source.read_bytes())
        self.assertEqual(footage.get_cached_video('pexels-101'), cached)
        with footage.connect() as connection:
            row = connection.execute(
                'SELECT size_bytes,sha256,access_count FROM local_cache WHERE asset_id=?',
                ('pexels-101',),
            ).fetchone()
        self.assertEqual(row['size_bytes'], source.stat().st_size)
        self.assertEqual(row['sha256'], hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertEqual(row['access_count'], 2)

    def test_cache_rejects_missing_and_empty_source(self):
        with self.assertRaisesRegex(ValueError, 'missing or empty'):
            footage.download_video(self.root / 'missing.mp4', 'pexels-102')
        empty = self.root / 'empty.mp4'
        empty.touch()
        with self.assertRaisesRegex(ValueError, 'missing or empty'):
            footage.download_video(empty, 'pexels-103')

    def test_cache_cleanup_evicts_oldest_entries_after_insert(self):
        old = self.root / 'old.mp4'
        old.write_bytes(b'old cache item')
        footage.download_video(old, 'pexels-old')
        with footage.connect() as connection:
            connection.execute(
                'UPDATE local_cache SET last_accessed=? WHERE asset_id=?',
                (time.time() - 10, 'pexels-old'),
            )

        new = self.root / 'new.mp4'
        new.write_bytes(b'new cache item')
        with patch.object(footage, 'MAX_LOCAL_CACHE_GB', 0.00000002):
            footage.download_video(new, 'pexels-new')

        self.assertFalse((self.local / 'pexels-old.mp4').exists())
        self.assertTrue((self.local / 'pexels-new.mp4').exists())
        with footage.connect() as connection:
            rows = connection.execute('SELECT asset_id FROM local_cache').fetchall()
        self.assertEqual([row['asset_id'] for row in rows], ['pexels-new'])


if __name__ == '__main__':
    unittest.main()
