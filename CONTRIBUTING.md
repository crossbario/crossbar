# Contributing

We welcome contributions to **Crossbar.io**! This guide explains how to get involved.

## Getting in Touch

- **GitHub Issues**: Report bugs or request features at
  https://github.com/crossbario/crossbar/issues
- **GitHub Discussions**: Ask questions and discuss at
  https://github.com/crossbario/crossbar/discussions

## Filing Issues

We track **issues** in the GitHub issue tracker [here](https://github.com/crossbario/crossbar/issues).

An issue is either a **bug** (an unexpected / unwanted behavior of the software or incorrect documentation) or a **feature** (a desire for new functionality / behavior in the software or new documentation).

A **question** though is *not* an issue - please use GitHub Discussions for questions.

### Filing Bugs

When reporting issues, please include:

1. Crossbar.io version (`crossbar version`)
2. Python version (`python --version`)
3. Operating system and version
4. Crossbar.io node configuration (sanitized)
5. Minimal steps to reproduce the issue
6. Full traceback if applicable

### Filing Features

When proposing a new **feature**, please provide:

1. Your actual **use case** and your **goals**
2. *Why* this is important for you
3. Optionally, a proposed solution

## Contributing Code

1. **Fork the repository** on GitHub
2. **Create a feature branch** from `master`
3. **Make your changes** following the code style
4. **Add tests** for new functionality
5. **Run the test suite** to ensure nothing is broken
6. **Submit a pull request** referencing any related issues

We use the Fork & Pull Model. This means that you fork the repo, make changes to your fork, and then make a pull request here on the main repo.

### Contributor Assignment Agreement

Before you can contribute any changes to the Crossbar.io project, we need a CAA (Contributor Assignment Agreement) from you.

The CAA gives us the rights to your code, which we need e.g. to react to license violations by others, for possible future license changes and for dual-licensing of the code.

#### What we need you to do

1. Download the [Individual CAA (PDF)](https://github.com/crossbario/crossbar/raw/master/legal/individual_caa.pdf).
2. Fill in the required information that identifies you and sign the CAA.
3. Scan the CAA to PNG, JPG or TIFF, or take a photo of the box on page 2.
4. Email the scan or photo to `contact@crossbario.com` with the subject line "Crossbar.io project contributor assignment agreement"

*If you write contributions as part of your work for a company, you also need to send us an [Entity CAA (PDF)](https://github.com/crossbario/crossbar/raw/master/legal/entity_caa.pdf) signed by somebody responsible in the company.*

**You only need to do this once - all future contributions are covered!**

## Development Setup

```bash
git clone https://github.com/crossbario/crossbar.git
cd crossbar
pip install -e .[dev]
```

## Running Tests

```bash
# Run all tests
tox

# Run tests for specific Python version
tox -e py312
```

## Code Style

- Follow PEP 8
- Use meaningful variable and function names
- Add docstrings for public APIs
- Keep lines under 100 characters

## License

By contributing to Crossbar.io, you agree that your contributions will be
licensed under the EUPL-1.2 License. See the [LICENSE](LICENSE) file for details.
