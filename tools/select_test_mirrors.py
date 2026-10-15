#!/usr/bin/env python3
"""Select lifecycle-test download sources using public-IP country geolocation."""
import os
import re
import sys
import urllib.request


def detect_country():
    # A proxy's exit country may differ from the machine's location.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for url in ('https://ipapi.co/country/', 'https://ipinfo.io/country'):
        try:
            with opener.open(url, timeout=3) as response:
                country = response.read(32).decode('ascii').strip().upper()
            if re.fullmatch(r'[A-Z]{2}', country):
                return country
        except (OSError, ValueError, UnicodeError):
            continue
    return 'unknown'


def select_sources(environment, country):
    china = country == 'CN'
    image = 'docker.1ms.run/library/ubuntu:26.10' if china else 'ubuntu:26.10'
    mirror = 'http://mirrors.tuna.tsinghua.edu.cn/ubuntu' if china else ''
    return (environment.get('WIFI_RELAY_TEST_IMAGE', image),
            environment.get('WIFI_RELAY_APT_MIRROR', mirror))


def main():
    country = os.environ.get('WIFI_RELAY_COUNTRY', '').strip().upper()
    if country and not re.fullmatch(r'[A-Z]{2}', country):
        sys.exit('WIFI_RELAY_COUNTRY must be a two-letter country code.')
    if not country:
        country = detect_country()
    image, mirror = select_sources(os.environ, country)
    if any(character in image + mirror for character in '|\n\r'):
        sys.exit('Download source overrides must not contain pipes or newlines.')
    print(f'{country}|{image}|{mirror}')


if __name__ == '__main__':
    main()
