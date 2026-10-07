# HTTPS verification through ADB

`RelayHttpsProbe.java` runs on Android without installing an app. It binds the
TCP socket to the supplied Wi-Fi IPv4 address, uses Android's default TLS trust
store, enables HTTPS hostname validation, and reports the HTTP status and received
body length. It does not use a proxy, relax certificate checks, or print addresses,
passwords, response bodies, or device identities.

Connect the Android client to the hotspot and wait for DHCP. Choose the authorized
ADB device and its hotspot address explicitly; binding to that address prevents
a successful request over a different client interface from satisfying the test.
Record the client's route and current Wi-Fi connection before and after the test.

From the repository root, with a JDK and Android SDK build-tools installed:

```sh
relay_android_sdk=/path/to/android-sdk
relay_android_client=DEVICE_ID
relay_android_address=192.168.12.CLIENT
mkdir -p dist/android-https/classes dist/android-https/dex
javac --release 8 -Xlint:-options -d dist/android-https/classes \
  tools/android/RelayHttpsProbe.java tools/android/RelayDnsProbe.java
"$relay_android_sdk/build-tools/36.0.0/d8" --min-api 26 \
  --output dist/android-https/dex dist/android-https/classes/RelayHttpsProbe.class \
  dist/android-https/classes/RelayDnsProbe.class
jar cf dist/android-https/relay-https.jar -C dist/android-https/dex classes.dex
adb -s "$relay_android_client" push dist/android-https/relay-https.jar /data/local/tmp/wifi-relay-https-probe.jar
adb -s "$relay_android_client" shell chmod 444 /data/local/tmp/wifi-relay-https-probe.jar
adb -s "$relay_android_client" shell \
  "CLASSPATH=/data/local/tmp/wifi-relay-https-probe.jar app_process /system/bin RelayHttpsProbe $relay_android_address example.com"
```

Repeat with `www.kernel.org` for a second external endpoint. A successful result
requires a completed TLS handshake and a 2xx HTTPS response. The socket has
10-second connection and read timeouts; the response capture is bounded. ADB
runners should impose an overall timeout as well because DNS and successive reads
can take longer than one socket timeout.

For a negative validation check, `wrong.host.badssl.com` should fail at the `tls`
stage with `SSLHandshakeException`. A DNS or connection failure does not establish
that certificate validation worked. Never bypass verification to get a passing
result. Android's hostname-check behavior is described in the
[SSLParameters reference](https://developer.android.com/reference/javax/net/ssl/SSLParameters#setEndpointIdentificationAlgorithm(java.lang.String)).

Clean up and restore the client's previous Wi-Fi connection after testing:

```sh
adb -s "$relay_android_client" shell rm -f /data/local/tmp/wifi-relay-https-probe.jar
```

The initial tablet baseline and hotspot checks on 7 October 2026 passed. The
[live validation report](../../docs/networkmanager-live-validation.md) records
the tested route and remaining production gates. This is a developer test helper;
it changes no Relay or NetworkManager runtime behavior.

## Fresh DNS through the hotspot

Run `RelayDnsProbe` with the client address and hotspot DNS gateway:

```sh
adb -s "$relay_android_client" shell \
  "CLASSPATH=/data/local/tmp/wifi-relay-https-probe.jar app_process /system/bin RelayDnsProbe $relay_android_address 192.168.12.1"
```

The probe creates a unique name under `example.com` and sends an A query directly
to the gateway over a socket bound to the client's Wi-Fi address. It validates
the transaction ID, response bit, echoed question, and NXDOMAIN response (rcode 3),
using the [DNS wire format](https://www.rfc-editor.org/rfc/rfc1035.html#section-4.1).
That negative answer is expected for the generated nonexistent name. A packet
capture on both hotspot and upstream interfaces should show the query being
forwarded and the response returning; this establishes a fresh exchange beyond
the hotspot's local cache. Keep raw captures private and remove them after saving
sanitized evidence.

When a generated name returns NOERROR, record the answer and authority counts and
query that **same name** directly through the upstream resolver. An assumption that
every random `example.com` name returns NXDOMAIN is not reliable on all resolvers.
The probe retains its strict NXDOMAIN assertion; a matching upstream NOERROR result
is evidence about upstream behavior, not a Relay forwarding failure. Keep positive
HTTPS resolution and certificate validation as separate checks.
