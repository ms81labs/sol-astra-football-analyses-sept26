"""Trusted single-threaded post-exec launcher; never a preexec_fn callback.

Invoked by media_execution with controller-authored argv. No app imports, shell,
request-selected launcher, model loading or service startup occurs here.
"""
from __future__ import annotations

import hashlib
import json
import os
import resource
import sys


def main() -> None:
    receipt_fd = int(sys.argv[1])
    limits = json.loads(sys.argv[2])
    expected_sha, binary = sys.argv[3:5]
    if not os.path.isabs(binary) or set(limits) != {"RLIMIT_CPU", "RLIMIT_AS", "RLIMIT_FSIZE"}:
        raise ValueError("invalid controller launch contract")
    for name, pair in limits.items():
        if len(pair) != 2 or any(type(n) is not int or n <= 0 for n in pair) or pair[0] > pair[1]:
            raise ValueError("invalid resource limit")
        resource.setrlimit(getattr(resource, name), tuple(pair))
    digest = hashlib.sha256()
    with open(binary, "rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != expected_sha:
        raise ValueError("media executable changed before execution")
    actual = {name: list(resource.getrlimit(getattr(resource, name))) for name in limits}
    data = json.dumps(actual, separators=(",", ":")).encode()
    if os.write(receipt_fd, data) != len(data):
        raise OSError("incomplete limit receipt")
    os.close(receipt_fd)  # The media program cannot author this evidence.
    os.execv(binary, [binary, *sys.argv[5:]])


if __name__ == "__main__":
    main()
