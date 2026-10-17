"""Export non-overlapping committed changes for local review; no fetch or merge."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def prepare(repo, base, components, output):
    repo, output = Path(repo).resolve(), Path(output).resolve()
    root = Path(git(repo, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
    if output == root or root in output.parents:
        raise ValueError('output_must_be_outside_repository')
    if output.exists():
        raise FileExistsError(output)
    # Only full immutable commit IDs: no branch drift, options or network fetch.
    for sha in [base, *components]:
        if not re.fullmatch(r'[0-9a-f]{40}', sha):
            raise ValueError('full_commit_sha_required')
        git(repo, 'cat-file', '-e', sha + '^{commit}')
    if not components or len(set(components)) != len(components):
        raise ValueError('distinct_components_required')
    changes = {}
    for sha in components:
        subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', base, sha], check=True)
        paths = git(repo, 'diff', '--name-only', '--no-renames', '-z', base, sha).decode().split('\0')
        for name in filter(None, paths):
            if name in changes:
                raise ValueError('overlapping_component_path:' + name)
            changes[name] = sha
    # Read archives, never execute source or use tar extraction with arbitrary paths.
    def archive(sha):
        files = {}
        with tarfile.open(fileobj=io.BytesIO(git(repo, 'archive', '--format=tar', sha))) as tar:
            for item in tar:
                p = PurePosixPath(item.name)
                if p.is_absolute() or '..' in p.parts or '.git' in p.parts:
                    raise ValueError('unsafe_archive_path')
                if item.isdir():
                    continue
                if not item.isfile():
                    raise ValueError('non_regular_archive_entry:' + item.name)
                files[item.name] = (tar.extractfile(item).read(), item.mode & 0o777)
        return files
    files = archive(base)
    for sha in components:
        incoming = archive(sha)
        for name, owner in changes.items():
            if owner == sha:
                if name in incoming:
                    files[name] = incoming[name]
                else:
                    files.pop(name, None)
    manifest = {'schema_version': 'keirin-integrated-candidate-v1',
                'base': base, 'components': components, 'changed_paths': changes,
                'merged': False, 'deployed': False, 'verification': 'not_run',
                'files': {name: hashlib.sha256(data).hexdigest()
                          for name, (data, _) in sorted(files.items())}}
    output.mkdir(parents=True, exist_ok=False)
    for name, (data, mode) in files.items():
        target = output / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(mode)
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, default=Path.cwd())
    parser.add_argument('--base', required=True)
    parser.add_argument('--component', action='append', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.repository, args.base, args.component, args.output_dir)
    print(json.dumps({k: v for k, v in result.items() if k not in ('files', 'changed_paths')}))


if __name__ == '__main__':
    main()
