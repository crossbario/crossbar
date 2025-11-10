from pygments.lexer import RegexLexer, bygroups, words
from pygments.token import *


class JustLexer(RegexLexer):
    """Lexer for Just command runner syntax."""

    name = "Just"
    aliases = ["just", "justfile"]
    filenames = ["justfile", "Justfile", "*.just"]

    tokens = {
        "root": [
            # Comments
            (r"#.*$", Comment.Single),
            # Recipe definitions
            (
                r"^(@?)([a-zA-Z_][a-zA-Z0-9_-]*)((?:\s+\w+)*)?(\s*:)",
                bygroups(Punctuation, Name.Function, Name.Variable, Punctuation),
            ),
            # Variable assignments
            (r"^([a-zA-Z_][a-zA-Z0-9_-]*)\s*(:=|=)", bygroups(Name.Variable, Operator)),
            # Built-in functions
            (
                words(
                    (
                        "justfile_directory",
                        "env_var",
                        "env_var_or_default",
                        "invocation_directory",
                        "quote",
                        "replace",
                        "trim",
                        "uppercase",
                        "lowercase",
                    ),
                    suffix=r"\b",
                ),
                Name.Builtin,
            ),
            # String interpolation
            (r"\{\{[^}]+\}\}", String.Interpol),
            # Strings
            (r'"[^"]*"', String.Double),
            (r"'[^']*'", String.Single),
            # Shell commands (lines starting with @)
            (r"^(\s*)(@)", bygroups(Text, Punctuation)),
            # Keywords
            (words(("if", "else", "export", "set"), suffix=r"\b"), Keyword),
            # Numbers
            (r"\b\d+\b", Number),
            # Operators
            (r"[+\-*/=<>!]+", Operator),
            # Everything else
            (r".", Text),
        ]
    }
