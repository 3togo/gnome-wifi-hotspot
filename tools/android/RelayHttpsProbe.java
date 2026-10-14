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
    private static String socketError(Exception exception) {
        String message = String.valueOf(exception.getMessage());
        for (String code : new String[] {"ECONNREFUSED", "ENETUNREACH", "EHOSTUNREACH", "ETIMEDOUT", "EADDRNOTAVAIL"}) {
            if (message.contains(code)) { return code; }
        }
        return "unspecified";
    }

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
            stage = "wifi_network";
            RelayWifiNetwork network = RelayWifiNetwork.forSource(source);
            stage = "dns";
            InetAddress target = null;
            for (InetAddress address : network.resolve(host)) {
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
                network.bind(raw);
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
                    RelayHttpResponse response = RelayHttpResponse.read(tls.getInputStream());
                    int status = response.status;
                    System.out.println("{\"success\":" + (status >= 200 && status < 300)
                        + ",\"https_status\":" + status
                        + ",\"certificate_and_hostname_verified\":true,\"source_bound\":true"
                        + ",\"wifi_network_bound\":true,\"tls_protocol\":\"" + tls.getSession().getProtocol()
                        + "\",\"body_bytes_received\":" + response.bodyBytes + ",\"response_complete\":" + response.complete + "}");
                    if (status < 200 || status >= 300) {
                        System.exit(1);
                    }
                }
            }
        } catch (Exception exception) {
            if (exception instanceof java.lang.reflect.InvocationTargetException
                    && exception.getCause() instanceof Exception) {
                exception = (Exception) exception.getCause();
            }
            // Report the failure category without addresses or client identities.
            System.out.println("{\"success\":false,\"stage\":\"" + stage
                + "\",\"error_type\":\"" + exception.getClass().getSimpleName() + "\""
                + ",\"socket_error\":\"" + socketError(exception) + "\"}");
            System.exit(1);
        }
    }
}
