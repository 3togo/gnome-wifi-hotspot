import java.io.ByteArrayOutputStream;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import javax.net.ssl.SSLParameters;
import javax.net.ssl.SSLSocket;
import javax.net.ssl.SSLSocketFactory;

/** ADB client probe: platform trust, HTTPS hostname validation, explicit source IP. */
public final class RelayHttpsProbe {
    public static void main(String[] args) {
        String stage = "arguments";
        try {
            if (args.length != 2) {
                throw new IllegalArgumentException("Expected source IPv4 address and HTTPS hostname");
            }
            InetAddress source = InetAddress.getByName(args[0]);
            String host = args[1];
            if (!(source instanceof Inet4Address) || !host.matches("[A-Za-z0-9.-]+")) {
                throw new IllegalArgumentException("Invalid source IPv4 address or hostname");
            }
            stage = "dns";
            InetAddress target = null;
            for (InetAddress address : InetAddress.getAllByName(host)) {
                if (address instanceof Inet4Address) {
                    target = address;
                    break;
                }
            }
            if (target == null) {
                throw new IllegalArgumentException("No IPv4 destination");
            }
            stage = "connect";
            try (Socket raw = new Socket()) {
                raw.bind(new InetSocketAddress(source, 0));
                raw.connect(new InetSocketAddress(target, 443), 10000);
                raw.setSoTimeout(10000);
                stage = "tls";
                SSLSocketFactory factory = (SSLSocketFactory) SSLSocketFactory.getDefault();
                try (SSLSocket tls = (SSLSocket) factory.createSocket(raw, host, 443, true)) {
                    SSLParameters parameters = tls.getSSLParameters();
                    parameters.setEndpointIdentificationAlgorithm("HTTPS");
                    tls.setSSLParameters(parameters);
                    tls.setSoTimeout(10000);
                    tls.startHandshake();
                    stage = "http";
                    String request = "GET / HTTP/1.1\r\nHost: " + host
                        + "\r\nConnection: close\r\n\r\n";
                    tls.getOutputStream().write(request.getBytes(StandardCharsets.US_ASCII));
                    tls.getOutputStream().flush();
                    ByteArrayOutputStream response = new ByteArrayOutputStream();
                    byte[] buffer = new byte[4096];
                    int count;
                    while (response.size() < 65536 && (count = tls.getInputStream().read(buffer)) != -1) {
                        response.write(buffer, 0, count);
                    }
                    String message = new String(response.toByteArray(), StandardCharsets.ISO_8859_1);
                    String firstLine = message.split("\r\n", 2)[0];
                    if (!firstLine.matches("HTTP/1\\.[01] [0-9]{3}.*")) {
                        throw new IllegalStateException("Invalid HTTP response");
                    }
                    int status = Integer.parseInt(firstLine.substring(9, 12));
                    int headersEnd = message.indexOf("\r\n\r\n");
                    if (headersEnd < 0) {
                        throw new IllegalStateException("Incomplete HTTP headers");
                    }
                    System.out.println("{\"success\":" + (status >= 200 && status < 300)
                        + ",\"https_status\":" + status
                        + ",\"certificate_and_hostname_verified\":true,\"source_bound\":true"
                        + ",\"tls_protocol\":\"" + tls.getSession().getProtocol()
                        + "\",\"body_bytes_received\":" + (response.size() - headersEnd - 4) + "}");
                    if (status < 200 || status >= 300) {
                        System.exit(1);
                    }
                }
            }
        } catch (Exception exception) {
            // Report the failure category without addresses or client identities.
            System.out.println("{\"success\":false,\"stage\":\"" + stage
                + "\",\"error_type\":\"" + exception.getClass().getSimpleName() + "\"}");
            System.exit(1);
        }
    }
}
