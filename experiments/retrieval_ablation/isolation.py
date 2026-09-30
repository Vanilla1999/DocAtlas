"""Linux namespace worker with read-only runtime/public inputs and no gold mount.

Requires util-linux user/mount/network/PID namespaces. No unsandboxed fallback.
This is an experimental trusted-code worker, not a multi-tenant execution API.
Review data must live outside the installed Python/system runtime directories.
"""
from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile


class IsolationUnavailable(RuntimeError):
    pass


_READY = '__DOCATLAS_ISOLATED_V1__\n'


def _literal_path(path: Path) -> Path:
    path = path.absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('symlink sandbox input/output path')
    if not path.is_dir():
        raise ValueError('sandbox mount must be an existing directory')
    return path


def run_isolated(code: str, *, app: Path, public: Path, output: Path,
                 timeout: int = 120) -> subprocess.CompletedProcess:
    """Run trusted Python code; close inherited FDs, scrub env, drop all caps."""
    if sys.platform != 'linux':
        raise IsolationUnavailable('Linux namespace worker required')
    if not isinstance(code, str) or type(timeout) is not int or timeout < 1:
        raise ValueError('invalid worker code/timeout')
    tools = {name: shutil.which(name) for name in ('unshare', 'mount', 'chroot', 'setpriv')}
    if not all(tools.values()):
        raise IsolationUnavailable('unshare, mount, chroot and setpriv are required')
    app, public, output = map(_literal_path, (app, public, output))
    for left, right in ((app, public), (app, output), (public, output)):
        if left.is_relative_to(right) or right.is_relative_to(left):
            raise ValueError('sandbox mounts must be disjoint')
    # Only runtime roots are exposed. Never bind host /, /home, /tmp or /proc.
    runtimes = sorted({Path('/usr'), Path(sys.prefix), Path(sys.base_prefix)}, key=lambda p: len(p.parts))
    for path in runtimes:
        if path in (Path('/'), Path('/home'), Path('/tmp'), Path('/mnt')):
            raise IsolationUnavailable('runtime prefix is too broad')
        if any(p.is_relative_to(path) or path.is_relative_to(p) for p in (app, public, output)):
            raise ValueError('runtime and data mounts must be disjoint')
    runtimes = [p for i, p in enumerate(runtimes) if not any(p.is_relative_to(q) for q in runtimes[:i])]
    q = shlex.quote
    with tempfile.TemporaryDirectory(prefix='docatlas-isolation-') as temporary:
        root = Path(temporary) / 'root'
        root.mkdir()
        commands = [f'{q(tools["mount"])} --make-rprivate /',
                    f'{q(tools["mount"])} -t tmpfs -o nosuid tmpfs {q(str(root))}']

        def bind(source, target, readonly=True):
            dest = str(root) + str(target)
            commands.append('mkdir -p ' + q(dest))
            commands.append(f'{q(tools["mount"])} --bind {q(str(source))} {q(dest)}')
            opts = 'remount,bind,nosuid' + (',ro' if readonly else '')
            commands.append(f'{q(tools["mount"])} -o {opts} {q(dest)}')

        for prefix in runtimes:
            bind(prefix, prefix)
        for name in ('bin', 'sbin', 'lib', 'lib64'):
            host = Path('/') / name
            if host.is_symlink():
                commands.append(f'ln -s {q(os.readlink(host))} {q(str(root / name))}')
            elif host.exists():
                bind(host, host)
        bind(app, '/app')
        bind(public, '/public')
        bind(output, '/output', readonly=False)
        commands.append('mkdir -p ' + ' '.join(q(str(root / name)) for name in ('tmp/home', 'dev')))
        for name in ('null', 'urandom'):
            dest = root / 'dev' / name
            commands.extend((f'touch {q(str(dest))}',
                f'{q(tools["mount"])} --bind /dev/{name} {q(str(dest))}'))
        # No host procfs; no inherited directory descriptors; all capabilities
        # dropped after chroot, so the worker cannot remount or escape the root.
        inside = 'cd /app; printf ' + q(_READY) + '; exec ' + shlex.join([sys.executable, '-c', code])
        commands.append('exec ' + shlex.join([tools['chroot'], str(root), tools['setpriv'],
            '--no-new-privs', '--bounding-set=-all', '--inh-caps=-all', '--ambient-caps=-all',
            '/bin/sh', '-ceu', inside]))
        env = {'PATH': '/usr/bin:/usr/sbin:/bin:/sbin', 'HOME': '/tmp/home', 'TMPDIR': '/tmp',
               'LANG': 'C.UTF-8', 'PYTHONPATH': '/app', 'PYTHONNOUSERSITE': '1',
               'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONHASHSEED': '0',
               'DOCATLAS_OFFLINE': '1', 'DOCATLAS_AUTO_VECTORS': '0',
               'DOCATLAS_REGISTRY_API_URL': 'http://127.0.0.1:1'}
        cmd = [tools['unshare'], '--user', '--map-root-user', '--mount', '--net',
               '--pid', '--fork', '--kill-child=KILL', '/bin/sh', '-ceu', '\n'.join(commands)]
        process = subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            close_fds=True, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise IsolationUnavailable('isolated worker timeout; process group killed') from None
        if not stdout.startswith(_READY):
            raise IsolationUnavailable('namespace setup failed: ' + stderr[-2000:])
        return subprocess.CompletedProcess([sys.executable, '-c', '<trusted worker>'],
            process.returncode, stdout[len(_READY):], stderr)
