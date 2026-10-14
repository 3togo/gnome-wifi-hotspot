import java.net.DatagramSocket;
import java.net.InetAddress;
import java.net.Socket;

/** Android shell Wi-Fi selection shared by the DNS and HTTPS probes. */
final class RelayWifiNetwork {
    private final Object network;
    private final Class<?> networkClass;

    public static void main(String[] args) {
        try {
            if (args.length != 1) { throw new IllegalArgumentException("Expected source IPv4"); }
            forSource(InetAddress.getByName(args[0]));
            System.out.println("{\"success\":true,\"connected_wifi_network\":true}");
        } catch (Exception exception) {
            System.out.println("{\"success\":false,\"connected_wifi_network\":false}");
            System.exit(1);
        }
    }

    private RelayWifiNetwork(Object network, Class<?> networkClass) {
        this.network = network;
        this.networkClass = networkClass;
    }

    static RelayWifiNetwork forSource(InetAddress source) throws Exception {
        // Source binding alone does not select Android's network routing table.
        // Shell probes must pin DNS and TCP to the Wi-Fi Network, including
        // while Android is still validating it or prefers mobile data.
        Class.forName("android.os.Looper").getMethod("prepareMainLooper").invoke(null);
        Class<?> threadClass = Class.forName("android.app.ActivityThread");
        Object thread = threadClass.getMethod("systemMain").invoke(null);
        Object context = threadClass.getMethod("getSystemContext").invoke(thread);
        Class<?> contextClass = Class.forName("android.content.Context");
        Object manager = contextClass.getMethod("getSystemService", String.class).invoke(context, "connectivity");
        Class<?> managerClass = Class.forName("android.net.ConnectivityManager");
        Class<?> networkClass = Class.forName("android.net.Network");
        Class<?> infoClass = Class.forName("android.net.NetworkInfo");
        Class<?> linksClass = Class.forName("android.net.LinkProperties");
        Class<?> linkClass = Class.forName("android.net.LinkAddress");
        Object network = null;
        for (Object candidate : (Object[]) managerClass.getMethod("getAllNetworks").invoke(manager)) {
            Object info = managerClass.getMethod("getNetworkInfo", networkClass).invoke(manager, candidate);
            // A previous Wi-Fi Network can linger after a reconnect with the
            // same IPv4 address. Its routes and resolver are no longer usable.
            if (info == null || !(Boolean) infoClass.getMethod("isConnected").invoke(info)
                    || (Integer) infoClass.getMethod("getType").invoke(info) != 1) { continue; }
            Object links = managerClass.getMethod("getLinkProperties", networkClass).invoke(manager, candidate);
            if (links == null || !((String) linksClass.getMethod("getInterfaceName").invoke(links))
                .matches("wlan[0-9]+")) { continue; }
            for (Object link : (Iterable<?>) linksClass.getMethod("getLinkAddresses").invoke(links)) {
                if (source.equals(linkClass.getMethod("getAddress").invoke(link))) {
                    if (network != null && !network.equals(candidate)) {
                        throw new IllegalStateException("Ambiguous Wi-Fi source address");
                    }
                    network = candidate;
                }
            }
        }
        if (network == null) { throw new IllegalStateException("Source is not on a Wi-Fi Network"); }
        return new RelayWifiNetwork(network, networkClass);
    }

    InetAddress[] resolve(String host) throws Exception {
        return (InetAddress[]) networkClass.getMethod("getAllByName", String.class).invoke(network, host);
    }

    void bind(Socket socket) throws Exception {
        networkClass.getMethod("bindSocket", Socket.class).invoke(network, socket);
    }

    void bind(DatagramSocket socket) throws Exception {
        networkClass.getMethod("bindSocket", DatagramSocket.class).invoke(network, socket);
    }
}
