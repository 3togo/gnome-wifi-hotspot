"""Exercise the Android probe's HTTP framing on the JVM, without networking."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('javac') and shutil.which('java'), 'JDK required for Android probe parser tests')
class HttpFramingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.path = Path(cls.directory.name)
        fixture = cls.path / 'HttpFixture.java'
        fixture.write_text('''import java.io.*;
public class HttpFixture {
    public static void main(String[] args) throws Exception {
        byte[] bytes = java.util.Base64.getDecoder().decode(args[0]);
        InputStream input = new ByteArrayInputStream(bytes) {
            public synchronized int read() {
                if (available() == 0 && args[1].equals("no-eof")) {
                    throw new AssertionError("Read beyond framed response");
                }
                return super.read();
            }
            public synchronized int read(byte[] b, int off, int len) {
                if (available() == 0 && args[1].equals("no-eof")) {
                    throw new AssertionError("Read beyond framed response");
                }
                return super.read(b, off, len);
            }
        };
        RelayHttpResponse response = RelayHttpResponse.read(input);
        System.out.println(response.status + " " + response.bodyBytes + " " + response.complete);
    }
}''')
        subprocess.run(['javac', '--release', '8', '-Xlint:-options', '-d', str(cls.path),
                        *(str(path) for path in sorted((ROOT / 'tools/android').glob('*.java'))),
                        str(fixture)],
                       check=True, capture_output=True, timeout=30)

    def read(self, response, no_eof=True):
        import base64
        result = subprocess.run(['java', '-cp', str(self.path), 'HttpFixture',
                                 base64.b64encode(response).decode(), 'no-eof' if no_eof else 'eof'],
                                capture_output=True, text=True, timeout=10)
        return result

    def test_content_length_completes_without_waiting_for_connection_close(self):
        result = self.read(b'HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhello')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '200 5 true')

    def test_chunked_completes_with_trailers_without_waiting_for_close(self):
        result = self.read(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n'
                           b'5;test=yes\r\nhello\r\n0\r\nX-Test: done\r\n\r\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '200 5 true')

    def test_truncated_response_is_failure(self):
        for response in [b'HTTP/1.1 200 OK\r\n',
                         b'HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhi',
                         b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nhi']:
            with self.subTest(response=response):
                self.assertNotEqual(self.read(response, no_eof=False).returncode, 0)

    def test_invalid_framing_is_failure(self):
        for header, body in [(b'Content-Length: -1', b''),
                             (b'Content-Length: 1\r\nContent-Length: 2', b'hi'),
                             (b'Transfer-Encoding: chunked', b'bad size\r\n')]:
            with self.subTest(header=header):
                self.assertNotEqual(self.read(b'HTTP/1.1 200 OK\r\n' + header + b'\r\n\r\n' + body).returncode, 0)

    def test_close_delimited_body(self):
        result = self.read(b'HTTP/1.0 200 OK\r\n\r\nhello', no_eof=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '200 5 true')

    def test_capture_limit_is_explicit(self):
        result = self.read(b'HTTP/1.1 200 OK\r\nContent-Length: 70000\r\n\r\n' + b'x' * 65536)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '200 65536 false')
