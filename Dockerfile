# syntax=docker/dockerfile:1.6
#
# ioteapot — single image that compiles and runs WSN experiments described
# with the IoTeaPot Python framework on every supported backend (Cooja,
# Renode, FIT IoT-LAB, Local) and OS (Contiki-NG, RIOT, Embassy).

FROM debian:trixie-slim AS base

ARG DEBIAN_FRONTEND=noninteractive

ENV LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64

# ---------------------------------------------------------------------------
# OS packages: build tooling + JDK for Cooja + Python + USB / serial helpers
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        # core build / fetch
        build-essential ca-certificates curl wget git xz-utils bzip2 unzip \
        pkg-config make cmake ninja-build srecord gawk \
        # python (3.13 on trixie)
        python3 python3-pip python3-venv python3-dev \
        # cooja prerequisites
        openjdk-21-jdk-headless ant \
        # serial / USB / flashing
        libusb-1.0-0 libusb-1.0-0-dev libudev1 udev usbutils libftdi1-2 \
        # openocd — required by the Local backend for SWD debug probes
        # (nrf52840dk, cc2538dk, Zolertia Firefly, ...)
        openocd \
        # renode runtime deps (.NET self-contained binary)
        libicu76 libssl3 libgssapi-krb5-2 zlib1g \
        # USB device forwarding from remote hosts (usbip)
        usbip hwdata \
        # misc
        sudo locales tini procps less vim-tiny socat gosu \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Nordic nrf-udev rules — makes /dev/ttyACM* and SEGGER J-Link devices
# accessible without root.  Also suppresses ModemManager interference.
# ---------------------------------------------------------------------------
ARG NRF_UDEV_VER=1.0.1
RUN set -eux; \
    cd /tmp && \
    wget -nv "https://github.com/NordicSemiconductor/nrf-udev/releases/download/v${NRF_UDEV_VER}/nrf-udev_${NRF_UDEV_VER}-all.deb" -O nrf-udev.deb && \
    dpkg -i nrf-udev.deb && \
    rm nrf-udev.deb

# ---------------------------------------------------------------------------
# Gradle — apt's version is too old for Cooja; fetch a current release.
# ---------------------------------------------------------------------------
ARG GRADLE_VER=8.10.2
RUN set -eux; \
    cd /tmp && \
    wget -nv "https://services.gradle.org/distributions/gradle-${GRADLE_VER}-bin.zip" -O gradle.zip && \
    unzip -q gradle.zip -d /opt && \
    rm gradle.zip && \
    rm -rf "/opt/gradle-${GRADLE_VER}/docs" "/opt/gradle-${GRADLE_VER}/samples" 2>/dev/null || true && \
    ln -s "/opt/gradle-${GRADLE_VER}" /opt/gradle && \
    ln -s /opt/gradle/bin/gradle /usr/local/bin/gradle

# ---------------------------------------------------------------------------
# ARM GNU Toolchain 10.3-2021.10  (Contiki-NG, RIOT, Embassy)
# Same version Contiki-NG uses in its own CI Docker image.  Within the
# IoTeaPot healthcheck range (>=9, <=12.2.1).
# ---------------------------------------------------------------------------
ARG ARM_TC_VER=10.3-2021.10
RUN set -eux; \
    cd /tmp && \
    wget -nv "https://developer.arm.com/-/media/Files/downloads/gnu-rm/${ARM_TC_VER}/gcc-arm-none-eabi-${ARM_TC_VER}-x86_64-linux.tar.bz2" -O arm.tar.bz2 && \
    mkdir -p /opt/arm-none-eabi && \
    tar -xjf arm.tar.bz2 -C /opt/arm-none-eabi --strip-components=1 --no-same-owner && \
    rm arm.tar.bz2 && \
    rm -rf /opt/arm-none-eabi/share/doc \
           /opt/arm-none-eabi/share/man \
           /opt/arm-none-eabi/share/info \
           /opt/arm-none-eabi/share/gcc-arm-none-eabi/samples \
           /opt/arm-none-eabi/bin/arm-none-eabi-gdb-py \
           /opt/arm-none-eabi/bin/arm-none-eabi-gdb-add-index-py
ENV PATH="/opt/arm-none-eabi/bin:${PATH}"

# ---------------------------------------------------------------------------
# Legacy MSP430 (mspgcc 4.7.4) for Contiki-NG
# Provides the `msp430-gcc` command name expected by Contiki-NG's makefiles.
# ---------------------------------------------------------------------------
RUN set -eux; \
    cd /tmp && \
    wget -nv https://github.com/pjonsson/msp430gcc-binary/releases/download/v1.1/mspgcc-4.7.4-linux-x86_64.tar.bz2 -O mspgcc.tar.bz2 && \
    mkdir -p /opt/msp430-contiki && \
    tar -xjf mspgcc.tar.bz2 -C /opt/msp430-contiki --strip-components=1 --no-same-owner && \
    rm mspgcc.tar.bz2
ENV PATH="/opt/msp430-contiki/bin:${PATH}"

# ---------------------------------------------------------------------------
# Modern msp430-elf-gcc (RIOT toolchains release)
# Provides the `msp430-elf-gcc` command expected by RIOT.
# ---------------------------------------------------------------------------
ARG RIOT_TC_GCC=10.1.0
ARG RIOT_TC_PKG=18
ARG RIOT_TC_TAG=20200722112854-64162e7
RUN set -eux; \
    cd /tmp && \
    PKGVER="${RIOT_TC_GCC}-${RIOT_TC_PKG}" && \
    wget -nv "https://github.com/RIOT-OS/toolchains/releases/download/${PKGVER}-${RIOT_TC_TAG}/riot-msp430-elf-${PKGVER}.tgz" -O riot-msp430.tgz && \
    mkdir -p /opt && \
    tar -xzf riot-msp430.tgz -C /opt && \
    rm riot-msp430.tgz && \
    ln -s "/opt/riot-toolchain/msp430-elf/${PKGVER}" /opt/msp430-riot
ENV PATH="/opt/msp430-riot/bin:${PATH}"

# ---------------------------------------------------------------------------
# Renode (portable Linux tarball, self-contained .NET app)
# ---------------------------------------------------------------------------
ARG RENODE_VER=1.15.3
RUN set -eux; \
    cd /tmp && \
    wget -nv "https://github.com/renode/renode/releases/download/v${RENODE_VER}/renode-${RENODE_VER}.linux-portable.tar.gz" -O renode.tar.gz && \
    mkdir -p /opt/renode && \
    tar -xzf renode.tar.gz -C /opt/renode --strip-components=1 && \
    rm renode.tar.gz && \
    rm -rf /opt/renode/tests /opt/renode/Documentation 2>/dev/null || true && \
    ln -s /opt/renode/renode /usr/local/bin/renode

# ---------------------------------------------------------------------------
# Rust + Embassy toolchain (rustup, stable, ARM Cortex-M targets, probe-rs,
# defmt-print).  Installed system-wide under /opt/rust.
# ---------------------------------------------------------------------------
ENV RUSTUP_HOME=/opt/rust/rustup \
    CARGO_HOME=/opt/rust/cargo \
    PATH=/opt/rust/cargo/bin:${PATH}
RUN set -eux; \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | \
        sh -s -- -y --default-toolchain stable --profile minimal \
                 --no-modify-path; \
    rustup target add \
        thumbv6m-none-eabi \
        thumbv7m-none-eabi \
        thumbv7em-none-eabi \
        thumbv7em-none-eabihf \
        thumbv8m.main-none-eabihf; \
    rustup component add llvm-tools-preview; \
    cargo install --locked probe-rs-tools; \
    cargo install --locked defmt-print; \
    strip /opt/rust/cargo/bin/* 2>/dev/null || true; \
    rm -rf /opt/rust/cargo/registry /opt/rust/cargo/git /opt/rust/cargo/.crates*; \
    chmod -R a+rX /opt/rust

# ---------------------------------------------------------------------------
# Nordic nrfutil — standalone binary (replaces legacy nrfjprog).
# Downloads the launcher, then pre-installs the `device` and `nrf5sdk-tools`
# subcommands so they're available offline.
# ---------------------------------------------------------------------------
RUN set -eux; \
    curl -sSL https://files.nordicsemi.com/artifactory/swtools/external/nrfutil/executables/x86_64-unknown-linux-gnu/nrfutil \
         -o /usr/local/bin/nrfutil && \
    chmod +x /usr/local/bin/nrfutil && \
    nrfutil install device && \
    nrfutil install nrf5sdk-tools

# ---------------------------------------------------------------------------
# Python packages: IoTeaPot extras that aren't part of the core deps but
# that specific backends need.
#   - cc2538-bsl:  serial bootloader flasher for Zolertia Firefly / RE-Mote
# ---------------------------------------------------------------------------
RUN pip install --no-cache-dir \
        cc2538-bsl

# ---------------------------------------------------------------------------
# IoTeaPot itself — bind-mounted from the host at /opt/ioteapot.
#
# Rather than baking a fixed version into the image, the wrapper script
# mounts the host checkout at /opt/ioteapot and we install it in editable
# mode at first boot (see entrypoint.sh).  This way the image stays
# current with the developer's working tree.
RUN mkdir -p /opt/ioteapot

# ---------------------------------------------------------------------------
# Cleanup — strip docs/locales/caches that crept in across layers.
# ---------------------------------------------------------------------------
RUN set -eux; \
    rm -rf /var/lib/apt/lists/* \
           /var/cache/apt/archives/* \
           /var/cache/debconf/*-old \
           /var/log/* \
           /tmp/* /root/.cache; \
    find /usr/share/doc   -mindepth 1 -maxdepth 1 -not -name 'copyright' -exec rm -rf {} + ; \
    find /usr/share/man   -mindepth 1 -delete ; \
    find /usr/share/info  -mindepth 1 -delete ; \
    find /usr/share/locale -mindepth 1 -maxdepth 1 -not -name 'en*' -not -name 'C' -exec rm -rf {} + ; \
    find / -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true

# ---------------------------------------------------------------------------
# Non-root user, with USB / serial groups so bound-in /dev/tty* devices
# are accessible without sudo.
# ---------------------------------------------------------------------------
RUN groupadd -g 20 dialout-host 2>/dev/null || true && \
    useradd -m -u 1000 -s /bin/bash ioteapot && \
    usermod -aG dialout,plugdev,sudo ioteapot && \
    echo 'ioteapot ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/ioteapot

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /workspace
ENV CNG_PATH= \
    RIOT_PATH= \
    COOJA_PATH= \
    IOTLABM3_ARCH_PATH=

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
CMD ["bash"]
