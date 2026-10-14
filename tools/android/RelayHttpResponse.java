import java.io.EOFException;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

/** Bounded HTTP/1 response reader; a framed message does not require socket EOF. */
final class RelayHttpResponse {
    final int status;
    int bodyBytes;
    boolean complete;
    private static final int LIMIT = 65536;

    private RelayHttpResponse(int status) { this.status = status; }

    private static String line(InputStream input) throws IOException {
        byte[] bytes = new byte[16384];
        int size = 0;
        while (size < bytes.length) {
            int value = input.read();
            if (value < 0) { throw new EOFException("Incomplete HTTP line"); }
            bytes[size++] = (byte) value;
            if (size >= 2 && bytes[size - 2] == '\r' && value == '\n') {
                return new String(bytes, 0, size - 2, StandardCharsets.ISO_8859_1);
            }
        }
        throw new IOException("HTTP line too long");
    }

    private static int headers(InputStream input, String[] framing) throws IOException {
        int size = 0;
        while (true) {
            String header = line(input);
            size += header.length() + 2;
            if (size > 16384) { throw new IOException("HTTP headers too large"); }
            if (header.isEmpty()) { return size; }
            int colon = header.indexOf(':');
            if (colon <= 0) { throw new IOException("Invalid HTTP header"); }
            String name = header.substring(0, colon);
            String value = header.substring(colon + 1).trim();
            if (framing != null && name.equalsIgnoreCase("Content-Length")) {
                if (framing[0] != null && !framing[0].equals(value)) {
                    throw new IOException("Conflicting HTTP lengths");
                }
                framing[0] = value;
            }
            if (framing != null && name.equalsIgnoreCase("Transfer-Encoding")) {
                framing[1] = value;
            }
        }
    }

    private void bytes(InputStream input, long length) throws IOException {
        byte[] buffer = new byte[4096];
        while (length > 0 && bodyBytes < LIMIT) {
            int count = input.read(buffer, 0, (int) Math.min(Math.min(length, buffer.length), LIMIT - bodyBytes));
            if (count < 0) { throw new EOFException("Incomplete HTTP body"); }
            bodyBytes += count;
            length -= count;
        }
    }

    static RelayHttpResponse read(InputStream input) throws IOException {
        String first = line(input);
        if (!first.matches("HTTP/1\\.[01] [0-9]{3}( .*)?")) {
            throw new IOException("Invalid HTTP status");
        }
        RelayHttpResponse response = new RelayHttpResponse(Integer.parseInt(first.substring(9, 12)));
        String[] framing = new String[2];
        headers(input, framing);
        if (framing[1] != null) {
            if (!framing[1].equalsIgnoreCase("chunked")) {
                throw new IOException("Unsupported transfer encoding");
            }
            while (response.bodyBytes < LIMIT) {
                String chunk = line(input).split(";", 2)[0];
                if (!chunk.matches("[0-9a-fA-F]{1,15}")) { throw new IOException("Invalid chunk size"); }
                long size = Long.parseLong(chunk, 16);
                if (size == 0) {
                    headers(input, null);
                    response.complete = true;
                    break;
                }
                response.bytes(input, size);
                if (response.bodyBytes == LIMIT) { break; }
                if (!line(input).isEmpty()) { throw new IOException("Invalid chunk ending"); }
            }
        } else if (framing[0] != null) {
            if (!framing[0].matches("[0-9]{1,15}")) { throw new IOException("Invalid content length"); }
            long length = Long.parseLong(framing[0]);
            response.bytes(input, length);
            response.complete = response.bodyBytes == length;
        } else {
            byte[] buffer = new byte[4096];
            while (response.bodyBytes < LIMIT) {
                int count = input.read(buffer, 0, Math.min(buffer.length, LIMIT - response.bodyBytes));
                if (count < 0) { response.complete = true; break; }
                response.bodyBytes += count;
            }
        }
        return response;
    }
}
