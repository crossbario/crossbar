# REVIEW/ADDITIONS: WAMP Python Stack Modernization

## Dependency Chain

```
1. txaio              ← Foundation (Twisted/asyncio abstraction)
2. autobahn-python    ← WAMP client library
3. zlmdb              ← Database layer (LMDB + CFFI)
4. cfxdb              ← Crossbar DB access
5. wamp-xbr           ← XBR/Blockchain extensions
6. crossbar           ← WAMP Router (>160 transitive deps)
```

yes, this is true!

but it is missing this one:

```
0. wamp-proto         ← WAMP protocol specification. Also includes e.g. WAMP message testsuite cases!
```

which _is_ already used e.g. in autobahn-python (for test coverage),
and it is also missing these two:

```
0. wamp-ai            ← AI support files.
0. wamp-cicd          ← CI/CD support files.
```

which must be added for all of above as Git submodules! See below.

## Git Submodules and Hooks

every repo should have (at least) the following two submodules

1. https://github.com/wamp-proto/wamp-ai: Multi-repository workspace setup for AI assistants/agents specific configuration.
2. https://github.com/wamp-proto/wamp-cicd: Centralized reusable CI/CD (GitHub) helpers and workflows.

these should

- point to the latest version of each,
- reside in `.ai` and `.cicd` within the repo root

here is how that looks for the autobahn-python repo:

```
oberstet@amd-ryzen5:~/work/wamp/autobahn-python$ git submodule status
 7219c81b83dd9f9f45f87763edebe6eda7bce18a .ai (remotes/origin/HEAD)
 12db44cd395d1488e42f9eaa2b05ea454bc7600f .cicd (heads/main)
 ...
```

and for wamp-ai submodule:

```
oberstet@amd-ryzen5:~/work/wamp/autobahn-python/.ai$ git remote -v
origin  https://github.com/wamp-proto/wamp-ai.git (fetch)
origin  https://github.com/wamp-proto/wamp-ai.git (push)
oberstet@amd-ryzen5:~/work/wamp/autobahn-python/.ai$ git log -n1 --oneline
7219c81 (HEAD, origin/main, origin/HEAD) add hint to AI for accetable acknowledgement of assistance in Git comments
```

and for wamp-cicd submodule:

```
oberstet@amd-ryzen5:~/work/wamp/autobahn-python/.cicd$ git remote -v
origin  https://github.com/wamp-proto/wamp-cicd.git (fetch)
origin  https://github.com/wamp-proto/wamp-cicd.git (push)
oberstet@amd-ryzen5:~/work/wamp/autobahn-python/.cicd$ git log -n1 --oneline
12db44c (HEAD -> main, origin/main, origin/HEAD) Normalize line endings to Unix (LF) on both upload and download
```

no edits/changes should be made to the added git submodule in a repo other than bumbing the revision pointed to.

if there is a need to have addition or changes in one of 1. or 2., then this must be done to the origin repo - and the version pointed to from the git submodule needs to be bumped.

both repos 1. and 2. are also available on asgard1 as a working repo, and a bare repo for data exchange:

```
oberstet@asgard1:~/work/wamp/wamp-cicd$ pwd
/home/oberstet/work/wamp/wamp-cicd
oberstet@asgard1:~/work/wamp/wamp-cicd$ ls -la
total 20
drwxr-xr-x  7 oberstet oberstet   11 Nov 21 14:21 .
drwxr-xr-x 20 oberstet oberstet   22 Nov  9 12:23 ..
drwxr-xr-x  5 oberstet oberstet    5 Nov  7 17:09 actions
drwxr-xr-x  8 oberstet oberstet   16 Nov  8 14:20 .git
drwxr-xr-x  3 oberstet oberstet    3 Oct 11 01:03 .github
-rw-r--r--  1 oberstet oberstet 4688 Oct 11 01:03 .gitignore
-rw-r--r--  1 oberstet oberstet 1389 Oct 11 01:03 justfile
-rw-r--r--  1 oberstet oberstet 1095 Oct 11 01:03 LICENSE
drwxr-xr-x  3 oberstet oberstet    6 Nov 21 14:21 .pytest_cache
-rw-r--r--  1 oberstet oberstet 1351 Oct 11 01:03 README.md
drwxr-xr-x  2 oberstet oberstet    3 Oct 11 01:03 scripts
oberstet@asgard1:~/work/wamp/wamp-cicd$ git log -n5 --oneline
0be5637 (HEAD -> main, origin/main, origin/HEAD) Fix wheel matching to support manylinux2014 and universal2 wheels
f82df71 Fix wheel filename parsing to support PyPy and multi-platform wheels
6ed6913 Add keep-metadata parameter to check-release-fileset action
87f7875 Add check-release-fileset action for PyPI upload validation
12db44c Normalize line endings to Unix (LF) on both upload and download
oberstet@asgard1:~/work/wamp/wamp-cicd$ 
```

what can be seen from this example, the git submodule in autobahn-python/.cicd points to commit 12db44c, while the latest commit on the submodule's git repo origin is 0be5637 - thus *this is lagging behind*, and that *should* generally be fixed (always point to the latest version).

### WAMP-AI

this submodule contains a couple of AI assistance supporting files, such as providing AI priming / context for the project, linked with symlinks, eg *addressed to the AI itself*:

```
oberstet@amd-ryzen5:~/work/wamp/autobahn-python$ ls -la
...
lrwxrwxrwx  1 oberstet oberstet     20 Nov 23 13:57 CLAUDE.md -> .ai/AI_GUIDELINES.md
...
oberstet@amd-ryzen5:~/work/wamp/autobahn-python$ ls -la .gemini/
lrwxrwxrwx  1 oberstet oberstet   23 Nov 23 13:57 GEMINI.md -> ../.ai/AI_GUIDELINES.md
...
```

or *addressed to the human developer*:

```
oberstet@amd-ryzen5:~/work/wamp/autobahn-python$ ls -la
...
lrwxrwxrwx  1 oberstet oberstet     16 Nov 23 13:57 AI_POLICY.md -> .ai/AI_POLICY.md
...
```

these symlinks can be created using `just setup-repo` from the `<REPOROOT>/.ai` directory, eg see:

```
oberstet@amd-ryzen5:~/work/wamp/autobahn-python/.ai$ just

The Web Application Messaging Protocol: AI Support Module

Available recipes:
    add-repo-submodule    # Add AI submodule from `wamp-ai` to dir `.ai` in target repository (should be run from root dir in target repository).
    default               # List all recipes.
    setup-repo            # Setup AI policy & guideline files and Git hooks in this repository (should be run from `.ai` dir after adding submodule in target repository).
    setup-workspace       # Setup AI policy & guideline files in workspace (should be run from root dir in `wamp-ai` repository).
    update-repo-submodule # Update AI submodule following `wamp-ai` in dir `.ai` in this repository (should be run from `.ai` dir after adding submodule in target repository).
```

Running `just setup-repo` will create those symlinks above, and once created, they need to be added and committed to the repo itself.

Importantly (!), the just recipe will _also_ setup git hooks pointing to files within the git submodule!

```
oberstet@amd-ryzen5:~/work/wamp/autobahn-python$ git config core.hooksPath
.ai/.githooks
oberstet@amd-ryzen5:~/work/wamp/autobahn-python$ tree .ai/.githooks
.ai/.githooks
├── README.md
├── commit-msg
└── pre-push

1 directory, 3 files
oberstet@amd-ryzen5:~/work/wamp/autobahn-python$ 
```

thus, git hooks are reused (uniformely) across all WAMP related repos!

the two crucial git hooks are:

1. `.ai/.githooks/commit-msg`: Git commit-msg hook to enforce AI_POLICY.md - Prevents commits with AI co-authorship which violates our policy
2. `.ai/.githooks/pre-push`: Git pre-push hook to enforce AI_POLICY.md - Prevents AI assistants from pushing tags (tags should only be created by humans)

----

**WAMP-AI Bugs**

there are currently 2 bugs related to the Git pre-push hook:

- "Print note how to temporarily disable" (for humans, to actually tag): https://github.com/wamp-proto/wamp-ai/issues/1
- "Prevent commits to master/main branch" (_also_, for AIs): https://github.com/wamp-proto/wamp-ai/issues/2

and there is 1 bug related to audit files:

- "Add audit file template": https://github.com/wamp-proto/wamp-ai/issues/4


### WAMP-CICD

## GitHub Actions

all WAMP related projects are hosted on GitHub, and should make use of GitHub Actions for CI/CD *using GitHub hosted runners*.

here is how GitHub related files look like in autobahn-python:

```
oberstet@amd-ryzen5:~/work/wamp/autobahn-python$ tree .github/
.github/
├── ISSUE_TEMPLATE
│   ├── bug_report.md
│   ├── config.yml
│   └── feature_request.md
├── pull_request_template.md
├── scripts
│   ├── build-arm64-wheel.sh
│   └── rtd-download-artifacts.sh
├── templates
│   ├── discussion-post.md.j2
│   ├── pr-comment.md.j2
│   ├── release-development.md.j2
│   ├── release-nightly.md.j2
│   └── release-stable.md.j2
└── workflows
    ├── generate_summary.py
    ├── main.yml
    ├── release-post-comment.yml
    ├── release.yml
    ├── verify_conformance.py
    ├── wheels-arm64.yml
    ├── wheels-docker.yml
    ├── wheels.yml
    └── wstest.yml

5 directories, 20 files
oberstet@amd-ryzen5:~/work/wamp/autobahn-python$ 
``` 

The `.github/` directory is the place GitHub looks for:

- Workflow definitions (CI/CD using GitHub Actions)
- Templates for Issues and PRs
- Repository automation scripts
- Bot configuration (e.g., dependabot, stale issues, etc.)

### GitHub Issue and PR Templates

One can store reusable templates in a separate repo, but:

- ❌ GitHub will not follow symlinks inside .github/
- ❌ GitHub will not use templates from submodules automatically
- ❌ GitHub Actions does not expand templates from outside the repository root

So simply adding a submodule and symlinking into .github/ will not work reliably for Issue/PR templates. What _does_ work is:

- Keep templates in a shared repo or submodule
- Copy them into .github/ via a workflow step
- Commit when changed

**WAMP-CICD Bugs**

there is currently 1 bug related to the GitHub Issue and PR Templates:

- "Add reusable GitHub Issue and PR templates" https://github.com/wamp-proto/wamp-cicd/issues/1

and 1 bug related to audit files:

- "Add validate-audit-file reusable action": https://github.com/wamp-proto/wamp-cicd/issues/2
