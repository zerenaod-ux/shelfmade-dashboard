import json, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import minddoodles_buffer_publish as publisher

class AnimationDoodlesBufferPublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.private = self.root / 'private'
        self.private.mkdir(mode=0o700)
        self.connection = self.private / 'connection.json'
        self.hosting = self.private / 'hosting.json'
        rows = [{'platform': p, 'id': publisher.CHANNELS[p], 'handle': publisher.HANDLES[p]} for p in publisher.CHANNELS]
        self.connection.write_text(json.dumps({'brand': 'minddoodles', 'token': 'test-token', 'channels': rows}))
        self.connection.chmod(0o600)
        self.patches = [patch.object(publisher, 'PRIVATE', self.private),
                        patch.object(publisher, 'CONNECTION', self.connection),
                        patch.object(publisher, 'HOSTING', self.hosting),
                        patch.object(publisher, 'POSTS', self.private / 'short-posts.json')]
        for item in self.patches: item.start()

    def tearDown(self):
        for item in reversed(self.patches): item.stop()
        self.temp.cleanup()

    def test_buffer_channels_alone_do_not_claim_publish_ready(self):
        state = publisher.status()
        self.assertTrue(state['connected'])
        self.assertFalse(state['publishing_ready'])

    def test_separate_host_setup_is_private_and_enables_route(self):
        state = publisher.save_hosting({'cloud_name': 'anim-test', 'api_key': 'key_123', 'api_secret': 'secret_123'})
        self.assertTrue(state['publishing_ready'])
        self.assertEqual(self.hosting.stat().st_mode & 0o777, 0o600)

    def test_routes_only_to_animationdoodles_buffer_channels_and_labels_ai(self):
        instagram = publisher._payload('instagram', 'title', 'caption', 'https://example.test/short.mp4')
        tiktok = publisher._payload('tiktok', 'title', 'caption', 'https://example.test/short.mp4')
        self.assertEqual(instagram['channelId'], publisher.CHANNELS['instagram'])
        self.assertEqual(instagram['metadata']['instagram']['type'], 'reel')
        self.assertTrue(instagram['metadata']['instagram']['isAiGenerated'])
        self.assertEqual(tiktok['channelId'], publisher.CHANNELS['tiktok'])
        self.assertTrue(tiktok['metadata']['tiktok']['isAiGenerated'])
        self.assertEqual(instagram['mode'], 'shareNow')

    def test_uncertain_existing_submission_is_never_retried(self):
        saved = {'package_id': '2026-10-27', 'key': 'short1', 'platform': 'instagram',
                 'fingerprint': 'a' * 64, 'state': 'unknown', 'remote_id': None}
        (self.private / 'short-posts.json').write_text(json.dumps({'posts': [saved]}))
        (self.private / 'short-posts.json').chmod(0o600)
        with patch.object(publisher, '_upload', side_effect=AssertionError('must not upload again')) as upload:
            result = publisher.publish('instagram', 'title', 'caption', self.root / 'missing.mp4', 'a' * 64, '2026-10-27', 'short1')
        self.assertEqual(result['state'], 'unknown')
        upload.assert_not_called()

if __name__ == '__main__': unittest.main()
