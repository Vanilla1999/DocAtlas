"""Reproducible eval-only corpus construction; never called by product code."""
import argparse,json,hashlib,shutil,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from eval.evidence_quality_v2.runtime import save_json
from docmancer.docs.application.model_visible_projection import estimate_projection_tokens
parser=argparse.ArgumentParser(description='Reconstruct the frozen eval corpus from verified public input material.')
parser.add_argument('--input-root',type=Path,required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parent; upstream=args.input_root/'corpus'
selected={'fastapi': ['docs/en/docs/tutorial/background-tasks.md', 'docs/en/docs/tutorial/cors.md'], 'starlette': ['docs/background.md', 'docs/lifespan.md'], 'typer': ['docs/tutorial/parameter-types/bool.md', 'docs/tutorial/terminating.md'], 'pydantic': ['docs/concepts/strict_mode.md', 'docs/concepts/alias.md'], 'httpx': ['docs/advanced/timeouts.md', 'docs/environment_variables.md'], 'mkdocs': ['docs/user-guide/writing-your-docs.md'], 'ruff': ['docs/preview.md', 'docs/configuration.md'], 'uv': ['docs/pip/compatibility.md']}
# Each span is authored/reviewed from the pinned upstream document before any new retrieval output.
specs={
'fastapi':[
('When do FastAPI background tasks run relative to returning the response?', 'conditional',0,'You can define background tasks','a response.'),
('Может ли task function для BackgroundTasks быть обычной def, а не async def?', 'polarity',0,'It can be an `async def`','correctly.'),
('Which arguments does .add_task() receive and in what roles?', 'list',0,'`.add_task()` receives as arguments:','(`message="some notification"`).'),
('Can allow_credentials work with allow_origins=["*"] in CORSMiddleware, and what is the default?', 'conditional',1,'* `allow_credentials`','origins must be specified.'),
('What identifies a CORS preflight request and which response status codes can the middleware return?', 'workflow',1,'These are any `OPTIONS`','informational purposes.'),
('Из каких компонентов состоит origin в CORS?', 'definition',1,'An origin is the combination','(`80`, `443`, `8080`).'),
],
'starlette':[
('If one BackgroundTasks function raises an exception, what happens to later tasks and their ordering?', 'conditional',0,'The tasks are executed in order.','opportunity to be executed.'),
('Will Starlette serve incoming requests before its lifespan handler has run?', 'polarity',1,'Starlette will not start serving','lifespan has been run.'),
('Когда начинается lifespan teardown относительно connections и background tasks?', 'lifecycle',1,'The lifespan teardown will run','background tasks have completed.'),
('Is request state a deep or shallow copy of lifespan state?', 'contrast',1,'The `state` received on the requests','lifespan handler.'),
('How should I use TestClient to ensure lifespan runs in tests?', 'usage',1,'You should use `TestClient`','lifespan is called.'),
('Какая сигнатура BackgroundTask добавляет одну фоновую задачу к response?', 'api',0,'Used to add a single background task','`BackgroundTask(func, *args, **kwargs)`'),
],
 'typer':[
('Does raising typer.Exit() itself imply an error, and what is its default exit code?', 'polarity',1,'`typer.Exit()` takes an optional','there was no error.'),
('Как через typer.Exit сообщить терминалу об ошибке?', 'usage',1,'You can pass a `code`','execution of the program:'),
('What visible message distinguishes aborting a Typer program from a normal Exit?', 'contrast',1,'It works more or less the same','execution was aborted:'),
('How do I give a boolean option alternative positive and negative names such as --accept and --reject?', 'api',0,'We can do that by passing a single','separated by `/`:'),
('Как записать только отрицательное имя boolean option: важен ли пробел перед /?', 'exact_identifier',0,"Have in mind that it's a string",'not `"/-S"`.'),
('What happens to --no-force when I declare only the --force option?', 'conditional',0,'// And --no-force no longer exists','Error: No such option: --no-force'),
],
 'pydantic':[
('What can strict mode be enabled on, and what happens instead of coercing an incorrect type?', 'workflow',0,'To better support this use case','not of the correct type.'),
('Does a UUID string pass strict validation from JSON and from Python in the same way?', 'contrast',0,'Note that we are looser','but not from python:'),
('Перечисли способы включить strict mode, включая field, annotation, config и validation call.', 'list',0,'* [Passing `strict=True`','(#strict-mode-with-configdict)'),
('What is AliasPath used to specify for validation aliases?', 'api',1,'The `AliasPath` is used','using aliases. For example:'),
('How does AliasGenerator help use different naming conventions when loading and saving?', 'usage',1,'`AliasGenerator` is a class','aliases for each field individually.'),
('В чём различие alias_priority=1 и alias_priority=2?', 'polarity',1,'* `alias_priority=2`','* `alias_priority` not set:'),
],
 'httpx':[
('What is HTTPX default timeout behavior: how long and which exception?', 'default',0,'The default behavior is','network inactivity.'),
('How can I disable all timeouts by default on an HTTPX Client?', 'api',0,'client = httpx.Client(timeout=None)','Disable all timeouts by default.'),
('Назови четыре типа timeout в HTTPX и объясни, что ограничивает каждый.', 'list',0,'There are four different types','configured by the `limits` argument.'),
('What does pool timeout wait for, which exception is raised, and which argument limits connections?', 'conditional',0,'* The **pool** timeout','configured by the `limits` argument.'),
('How can HTTPX ignore environment variables for both a Client and top-level requests?', 'workflow',1,'Environment variables are used by default.','httpx.get("<url>", trust_env=False)`.'),
('Какие переменные задают прокси для http, https и всех запросов?', 'api',1,'`HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` set','requests respectively.'),
],
 'mkdocs':[
('Where do documentation sources and mkdocs.yml live by default?', 'path',0,'Your documentation source should be written','`mkdocs.yml` configuration file.'),
('What happens when index.md and README.md are in the same directory?', 'conditional',0,'If both an `index.md`','ignored.'),
('Are pages absent from nav still built, and what navigation links do they lose?', 'polarity',0,'Any pages not listed in your navigation','unless linked to directly.'),
('Относительно чего задаются пути в nav и где лежат index.md и about.md при docs_dir=docs?', 'path',0,'All paths in the navigation','`docs/about.md`.'),
('Which page title wins when the navigation configuration and Markdown content define different titles?', 'contrast',0,'Note that if a title is defined for a page','within the page itself.'),
('Can table cells contain block elements or multiple lines, and are blank lines around a table required?', 'table',0,'Note that table cells cannot contain','line before and after the table.'),
],
 'ruff':[
('Does enabling preview automatically enable all preview rules?', 'polarity',0,'Enabling preview mode does not on its own','selecting preview rules.'),
('Как включить Ruff preview через CLI или configuration file?', 'usage',0,'Preview mode can be enabled','configuration file.'),
('Since which version can preview be configured separately for linting and formatting?', 'version',0,'Preview mode can be configured separately','(requires Ruff v0.1.1+).'),
('What happens if a deprecated rule is explicitly selected while preview is enabled?', 'lifecycle',0,'When preview mode is enabled, deprecated rules','rule category or prefix.'),
('What happens to explicit-preview-rules when preview mode is disabled?', 'conditional',0,'If preview mode is not enabled','this setting has no effect.'),
('Does Ruff merge parent configuration files, and what explicit mechanism supports inheritance?', 'contrast',1,'Ruff does not merge settings','config file, like so:'),
],
 'uv':[
('Does uv read pip.conf or PIP_INDEX_URL?', 'polarity',0,'uv does not read configuration files','`pip.conf` or `PIP_INDEX_URL`.'),
('В каких двух случаях uv принимает pre-release версии по умолчанию?', 'list',0,'By default, uv will accept pre-release','a package are pre-releases.'),
('What can I do when dependency resolution fails due to a transitive pre-release?', 'workflow',0,'If dependency resolution fails due','for that specific dependency.'),
('How does uv restrict candidate versions across multiple indexes and why?', 'conditional',0,'When uv searches for a package','instead of the internal\npackage.'),
('Compare first-match, unsafe-first-match and unsafe-best-match index strategies.', 'list',0,'- `first-match` (default)','"dependency confusion" attacks.'),
('Which build isolation mode does uv use by default and what is the escape hatch for a missing build dependency?', 'workflow',0,'uv uses [PEP 517]','uv pip install wheel && uv pip install --no-build-isolation biopython==1.77'),
]}
manifest_all=json.loads((args.input_root/'source-manifest.json').read_text())
manifest=[]; cases=[]; licenses=[]
for project, files in selected.items():
 for relative in files:
  src=upstream/project/relative
  assert src.is_file(),src
  dst=root/'sources'/project/relative;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
  entry=next(row for row in manifest_all if row['project']==project and row['path']==relative)
  manifest.append(entry)
 for src in sorted((upstream/project).glob('LICENSE*')):
  if src.is_file():
   dst=root/'licenses'/project/src.name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
   licenses.append(str(dst.relative_to(root)))
 meta=next(x for x in manifest if x['project']==project)
 split='development' if project in ('fastapi','starlette','typer','pydantic') else 'frozen_validation_exposed'
 for i,(question,family,idx,start,end) in enumerate(specs[project],1):
  relative=files[idx];text=(upstream/project/relative).read_text();a=text.index(start);z=text.index(end,a)+len(end);span=text[a:z]
  part={'path':relative,'text':span,'line_start':text[:a].count('\n')+1,'line_end':text[:z].count('\n')+1}
  claim={'id':'required','witness_sets':[{'parts':[part]}]}
  case={'id':f'{project}-{i:02d}','question':question,'family':family,'project_group':project,'split':split,
     'source_kind':'real_upstream','policy':{'version':meta['ref'],'scope':'project','authority':'source_of_truth','lifecycle':'active'},
     'answerability':'within_budget','required_claims':[claim], 'forbidden_inferences':['Do not infer a rule for a different version or an unobserved local configuration.']}
  # Budget oracle counts a deliberately conservative retrieval-only envelope, not answer text.
  oracle={'kind':'docs_context','status':'ok','answer_supported':False,'answer_available':False,'edit_ready':False,
   'sources':[{'evidence_id':'oracle-0','path_or_url':relative,'snippet':span,'line_start':part['line_start'],'line_end':part['line_end'],'content_sha256':meta['sha256'],'version_binding':meta['ref']} ]}
  estimate=estimate_projection_tokens(oracle)
  case['budget_check']={'method':'conservative_source_span_envelope','estimated_tokens':estimate,'source_count':1}
  if estimate>800:case['answerability']='over_budget';case['budget_check']['reason']='minimal annotated relation exceeds envelope budget'
  cases.append(case)
 # Four predeclared non-full categories; not used to tune a desired success ratio.
 base=cases[-6]
 for n,kind,question in [
  (7,'partial',base['question']+' Also identify the exact value chosen in our private production deployment.'),
  (8,'unanswerable',f'What is the guaranteed 99th-percentile latency in milliseconds for our production {project} deployment?'),
  (9,'ambiguous',f'Which {project} configuration is best for our service? Our workload and deployment constraints are not specified.'),
  (10,'over_budget',f'Provide every documented workflow, caveat and complete code example verbatim from all {project} source files in this snapshot, without omissions.')]:
  c=json.loads(json.dumps(base));c.update(id=f'{project}-{n:02d}',question=question,family=kind,answerability=kind)
  if kind=='partial':c['required_claims'].append({'id':'private_configuration','witness_sets':[]});c['expected_response']='partial_with_explicit_gap'
  elif kind in ('unanswerable','ambiguous'):c['required_claims']=[{'id':'unknown_or_unspecified','witness_sets':[]}];c['expected_response']='abstention_or_clarification'
  else:
   parts=[{'path':rel,'text':(upstream/project/rel).read_text()} for rel in files]
   c['required_claims']=[{'id':'complete_source_extraction','witness_sets':[{'parts':parts}]}]
   c['source_kind']='real_upstream_budget_stress';c['expected_response']='honest_partial_budget'
  c['budget_check']={'method':'source_scope_review','full_answer_fits':False,'reason':kind}
  cases.append(c)
save_json(root/'cases.json',{'schema_version':'evidence-quality-frozen-80-v1','state':'frozen_development_benchmark','unseen_validation':'NOT_MEASURED','cases':cases})
save_json(root/'source-manifest.json',{'sources':manifest,'licenses':licenses,'source_transform':'NONE: exact full upstream Markdown files; external include directives not expanded','scope':'selected document snapshot, not every upstream document or rendered website'})
protocol=json.loads((root/'protocol.json').read_text())
assert hashlib.sha256((root/'cases.json').read_bytes()).hexdigest()==protocol['cases_sha256'], 'frozen cases drift'
assert hashlib.sha256((root/'source-manifest.json').read_bytes()).hexdigest()==protocol['source_sha256'], 'source manifest drift'
print('Frozen corpus reconstructed and hash verified:',len(cases))
