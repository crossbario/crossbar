# Development

Notes specific to **Crossbar.io**: the contributor assignment agreement, development setup, running
the tests, supported runtimes, release versioning, and the license. The contribution workflow shared
by all WAMP projects — GitHub issue first, red → green tests, and the AI-assistance disclosure — is in
[CONTRIBUTING.md](CONTRIBUTING.md).

## Reporting bugs

In addition to what CONTRIBUTING.md asks for, please include:

- the Crossbar.io version: `crossbar version`
- the node configuration, **sanitized** (remove secrets, keys and credentials)

## Contributor Assignment Agreement

Before you can contribute any changes to the Crossbar.io project, we need a CAA (Contributor Assignment Agreement) from you.

The CAA gives us the rights to your code, which we need e.g. to react to license violations by others, for possible future license changes and for dual-licensing of the code.

### What we need you to do

1. Download the [Individual CAA (PDF)](https://github.com/crossbario/crossbar/raw/master/legal/individual_caa.pdf).
2. Fill in the required information that identifies you and sign the CAA.
3. Scan the CAA to PNG, JPG or TIFF, or take a photo of the box on page 2.
4. Email the scan or photo to `contact@crossbario.com` with the subject line "Crossbar.io project contributor assignment agreement"

*If you write contributions as part of your work for a company, you also need to send us an [Entity CAA (PDF)](https://github.com/crossbario/crossbar/raw/master/legal/entity_caa.pdf) signed by somebody responsible in the company.*

**You only need to do this once - all future contributions are covered!**

## Development setup

Development is driven by [`just`](https://github.com/casey/just) and [`uv`](https://github.com/astral-sh/uv);
run `just` to list all recipes. Every recipe takes the name of a managed virtual environment:
`cpy314`, `cpy313`, `cpy312`, `cpy311` (CPython) or `pypy311` (PyPy).

```bash
git clone https://github.com/crossbario/crossbar.git
cd crossbar
git submodule update --init --recursive
just create cpy314
just install-dev cpy314
```

## Running the tests

```bash
just test cpy314              # the test suite
just test pypy311             # the same on PyPy
just test-functional cpy314   # functional tests
just check cpy314             # formatting, typing and the other checks
```

**Supported runtimes:** CPython 3.11–3.14 and PyPy 3.11. Crossbar.io must run on both **CPython and
PyPy**; run the relevant tests on both before submitting. Crossbar.io runs on Twisted.

## Code style

`ruff` enforces formatting and linting (`just check-format cpy314`); the line length is 119. Add
docstrings for public APIs, and type hints for new code (`just check-typing cpy314`).

## Documentation

The documentation is reStructuredText, built with Sphinx: `just docs cpy314`.

## Versioning

This project uses [CalVer](https://calver.org/) with PEP 440 development releases:
`YY.M.PATCH[.devN]`. The version is stored in `pyproject.toml` and `src/crossbar/_version.py`, kept in
sync with `just file-version`, `just bump-dev`, `just bump-next <version>` and `just prep-release`.
Git tags and releases are created by maintainers only.

## License

Crossbar.io is licensed under the **EUPL-1.2** (see [LICENSE](LICENSE)). By contributing, you agree
that your contributions are licensed under the EUPL-1.2, in addition to the contributor assignment
agreement above.
