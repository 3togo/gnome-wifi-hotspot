cmake_minimum_required(VERSION 3.16)
project(WifiRelay LANGUAGES NONE)

if(CMAKE_SOURCE_DIR STREQUAL CMAKE_BINARY_DIR)
    message(FATAL_ERROR "Use an out-of-source build: cmake -S . -B build")
endif()

# Keep package contents and version defaults in the existing Debian builder.
set(WIFI_RELAY_VERSION "" CACHE STRING
    "Debian package version (empty uses packaging/debian/changelog)")
set(WIFI_RELAY_BUILD_OUTPUT "${CMAKE_BINARY_DIR}/dist" CACHE PATH
    "Directory for the separate and bundled Debian packages")

foreach(tool bash python3 dpkg dpkg-deb dpkg-parsechangelog)
    find_program(WIFI_RELAY_TOOL_${tool} NAMES "${tool}")
    if(NOT WIFI_RELAY_TOOL_${tool})
        message(FATAL_ERROR
            "Missing ${tool}. Install Bash, Python 3, dpkg and dpkg-dev to build Debian packages.")
    endif()
endforeach()

set(package_version_args)
if(NOT WIFI_RELAY_VERSION STREQUAL "")
    list(APPEND package_version_args "${WIFI_RELAY_VERSION}")
endif()

# Always run the script so edits to any packaged file are picked up.
add_custom_target(deb ALL
    COMMAND "${CMAKE_COMMAND}" -E env
        "WIFI_RELAY_BUILD_OUTPUT=${WIFI_RELAY_BUILD_OUTPUT}"
        "${WIFI_RELAY_TOOL_bash}" "${CMAKE_SOURCE_DIR}/packaging/build-deb.sh"
        ${package_version_args}
    WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    COMMENT "Building Wi-Fi Relay Debian packages in ${WIFI_RELAY_BUILD_OUTPUT}"
    VERBATIM
    USES_TERMINAL
)
