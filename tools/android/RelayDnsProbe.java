import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.UUID;

/** Query a unique external name directly through the hotspot's DNS gateway. */
public final class RelayDnsProbe {
    public static void main(String[] args) {
        try {
            if (args.length != 2) {
                throw new IllegalArgumentException("Expected client IPv4 and DNS gateway");
            }
            String name = "relay-" + UUID.randomUUID().toString().replace("-", "") + ".example.com";
            int id = (int) (System.nanoTime() & 65535);
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            DataOutputStream query = new DataOutputStream(bytes);
            query.writeShort(id);
            query.writeShort(0x0100); // Recursion desired.
            query.writeShort(1);
            query.writeShort(0);
            query.writeShort(0);
            query.writeShort(0);
            for (String label : name.split("\\.")) {
                byte[] value = label.getBytes(StandardCharsets.US_ASCII);
                query.writeByte(value.length);
                query.write(value);
            }
            query.writeByte(0);
            query.writeShort(1); // A.
            query.writeShort(1); // IN.
            byte[] request = bytes.toByteArray();
            try (DatagramSocket socket = new DatagramSocket(null)) {
                socket.bind(new InetSocketAddress(InetAddress.getByName(args[0]), 0));
                socket.connect(InetAddress.getByName(args[1]), 53);
                socket.setSoTimeout(10000);
                socket.send(new DatagramPacket(request, request.length));
                byte[] buffer = new byte[4096];
                DatagramPacket response = new DatagramPacket(buffer, buffer.length);
                socket.receive(response);
                if (response.getLength() < request.length
                    || (((buffer[0] & 255) << 8) | (buffer[1] & 255)) != id
                    || (buffer[2] & 0x80) == 0
                    || !Arrays.equals(Arrays.copyOfRange(request, 12, request.length),
                                      Arrays.copyOfRange(buffer, 12, request.length))) {
                    throw new IllegalStateException("Invalid DNS response");
                }
                int rcode = buffer[3] & 15;
                int answers = ((buffer[6] & 255) << 8) | (buffer[7] & 255);
                int authorities = ((buffer[8] & 255) << 8) | (buffer[9] & 255);
                int additional = ((buffer[10] & 255) << 8) | (buffer[11] & 255);
                System.out.println("{\"success\":" + (rcode == 3)
                    + ",\"rcode\":" + rcode + ",\"answer_count\":" + answers
                    + ",\"authority_count\":" + authorities + ",\"additional_count\":" + additional
                    + ",\"response_bytes\":" + response.getLength()
                    + ",\"unique_query\":\"" + name
                    + "\",\"gateway_queried\":true,\"source_bound\":true}");
                if (rcode != 3) {
                    System.exit(1);
                }
            }
        } catch (Exception exception) {
            System.out.println("{\"success\":false,\"error_type\":\""
                + exception.getClass().getSimpleName() + "\"}");
            System.exit(1);
        }
    }
}
