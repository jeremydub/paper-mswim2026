#!/usr/bin/env bash
# Entrypoint: align the in-container `ioteapot` user with the caller's host

set -euo pipefail

target_uid="${HOST_UID:-}"
target_gid="${HOST_GID:-}"

if [[ -n "${target_uid}" && -n "${target_gid}" ]]; then
    current_uid="$(id -u ioteapot)"
    current_gid="$(id -g ioteapot)"

    if [[ "${target_gid}" != "${current_gid}" ]]; then
        # The GID may already be in use (e.g. by `dialout`); reuse it then.
        existing_group="$(getent group "${target_gid}" | cut -d: -f1 || true)"
        if [[ -z "${existing_group}" ]]; then
            groupmod -g "${target_gid}" ioteapot
        else
            usermod -g "${existing_group}" ioteapot
        fi
    fi

    if [[ "${target_uid}" != "${current_uid}" ]]; then
        usermod -u "${target_uid}" ioteapot
        # /home/ioteapot was chowned at image build with the old UID.
        chown -R "${target_uid}:${target_gid}" /home/ioteapot 2>/dev/null || true
    fi

    # Make sure the user can read whatever was just bind-mounted at /workspace
    # (we don't chown the mount itself; that would corrupt host ownership).

    exec gosu ioteapot "$@"
fi

exec "$@"
