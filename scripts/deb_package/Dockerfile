# The machine `nox -s deb-package` installs the .deb on: a release with systemd as its init, so the
# maintainer scripts reach real user managers, and one user, player, whose models and settings an
# upgrade must keep (plans/lucid-circuit-linux.md, section 7). RELEASE is the image: the release
# that built the .deb, or a newer one.
ARG RELEASE=ubuntu:26.04
FROM ${RELEASE}
# Over IPv4: Docker's IPv6 often reaches no mirror, and apt then waits on each one
RUN apt-get -o Acquire::ForceIPv4=true update \
    && DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::ForceIPv4=true install -y \
        --no-install-recommends systemd systemd-sysv dbus dbus-user-session libpam-systemd \
    && useradd --create-home player \
    && rm -rf /var/lib/apt/lists/*
CMD ["/sbin/init"]
