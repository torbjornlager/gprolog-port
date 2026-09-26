"""Run the connection-boundary checks under address/undefined sanitizers."""
from pathlib import Path
import os
import shlex
import subprocess
import tempfile
root=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='outbound-socket-') as tmp:
    binary=Path(tmp)/'check'
    subprocess.run([*shlex.split(os.environ.get('CC','cc')),'-std=c11','-D_POSIX_C_SOURCE=200809L','-D_DARWIN_C_SOURCE','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',str(root/'outbound_socket_tests.c'),'-lcurl','-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
