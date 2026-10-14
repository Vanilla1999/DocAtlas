import base64, hashlib, json, os, pathlib, subprocess

def git(*args, **kwargs):
    return subprocess.check_output(['git', *args], text=True, **kwargs).strip()

helper = pathlib.Path(os.environ['RUNNER_TEMP']) / 'final.py'
helper.write_text(git('show', 'HEAD:.pr211-workspace/final.py') + '\n')
# Exact product SHA copied from the preceding integration archive's head.txt.
base = '5dcbc5eb5013b84a44e777492a2238f3d94ff1a6'
git('checkout', '--detach', base)
subprocess.run(['python', str(helper)], check=True)
paths = ['tests/test_heuristic_removal_public_integration.py', 'tests/test_project_context_quality_v2_protocol.py']
assert set(git('diff', '--name-only').splitlines()) == set(paths)
git('diff', '--check')
results = pathlib.Path(os.environ['RUNNER_TEMP']) / 'assembly'
results.mkdir()
(results / 'repair.patch').write_text(git('diff') + '\n')
(results / 'hashes.json').write_text(json.dumps({p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in paths}, indent=2))
git('add', '--', *paths)
tree = git('write-tree')
author = dict(os.environ, GIT_AUTHOR_NAME='github-actions[bot]', GIT_AUTHOR_EMAIL='41898282+github-actions[bot]@users.noreply.github.com', GIT_COMMITTER_NAME='github-actions[bot]', GIT_COMMITTER_EMAIL='41898282+github-actions[bot]@users.noreply.github.com')
candidate = git('commit-tree', tree, '-p', base, '-m', 'test: distinguish explicit resource quotas from native completeness in public integration', env=author)
(results / 'candidate.txt').write_text(candidate + '\n')
print('Candidate:', candidate)
branch = 'work/pr211-candidate-' + os.environ['GITHUB_RUN_ID']
auth = base64.b64encode(('x-access-token:' + os.environ['GH_TOKEN']).encode()).decode()
push_env = dict(os.environ, GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='http.https://github.com/.extraheader', GIT_CONFIG_VALUE_0='AUTHORIZATION: basic ' + auth)
subprocess.run(['git', 'push', 'origin', candidate + ':refs/heads/' + branch], env=push_env, check=True)
with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
    output.write('candidate=' + candidate + '\n')
