import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    'test_mirrors', Path(__file__).resolve().parents[1] / 'tools/select_test_mirrors.py')
mirrors = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mirrors)


class TestMirrorSelection(unittest.TestCase):
    def test_china_selects_both_regional_sources(self):
        image, apt = mirrors.select_sources({}, 'CN')
        self.assertEqual(image, 'docker.1ms.run/library/ubuntu:26.10')
        self.assertEqual(apt, 'http://mirrors.tuna.tsinghua.edu.cn/ubuntu')

    def test_other_and_unknown_countries_keep_distribution_sources(self):
        for country in ('US', 'DE', 'unknown'):
            self.assertEqual(mirrors.select_sources({}, country), ('ubuntu:26.10', ''))

    def test_explicit_sources_override_geolocation_including_empty_apt(self):
        self.assertEqual(mirrors.select_sources(
            {'WIFI_RELAY_TEST_IMAGE': 'local-image', 'WIFI_RELAY_APT_MIRROR': ''}, 'CN'),
            ('local-image', ''))

    def test_geolocation_uses_direct_connection_and_falls_back(self):
        with patch.object(mirrors.urllib.request, 'build_opener') as build:
            build.return_value.open.side_effect = [OSError('unavailable'), io.BytesIO(b'CN\n')]
            self.assertEqual(mirrors.detect_country(), 'CN')
            self.assertEqual(build.call_args.args[0].proxies, {})
            self.assertEqual(build.return_value.open.call_count, 2)

    def test_failed_geolocation_is_not_a_test_failure(self):
        with patch.object(mirrors.urllib.request, 'build_opener') as build:
            build.return_value.open.side_effect = OSError('offline')
            self.assertEqual(mirrors.detect_country(), 'unknown')
