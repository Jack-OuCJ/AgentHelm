"""TOML loading on Python 3.9+: older versions accept tables, scalar values and arrays."""
import json
import re

try:
    import tomllib
except ImportError:
    tomllib = None


# The configuration schema only needs strings, booleans, integers and arrays.
LEXEME = re.compile(r'"(?:[^"\\]|\\.)*"|\'[^\']*\'|\#[^\n]*|\s+|[\[\],=.]|[A-Za-z0-9_+-]+')


def loads(source):
    if tomllib is not None:
        return tomllib.loads(source)
    lexemes, end = [], 0
    for match in LEXEME.finditer(source):
        if source[end:match.start()].strip():
            raise ValueError('Unsupported TOML syntax; use Python 3.11+ for full TOML')
        lexeme = match[0]
        if not lexeme.isspace() and not lexeme.startswith('#'):
            lexemes.append(lexeme)
        end = match.end()
    if source[end:].strip():
        raise ValueError('Unsupported TOML syntax')
    position = 0

    def take():
        nonlocal position
        lexeme = lexemes[position]
        position += 1
        return lexeme

    def value():
        lexeme = take()
        if lexeme == '[':
            result = []
            while lexemes[position] != ']':
                result.append(value())
                if lexemes[position] != ',':
                    break
                take()
            if take() != ']':
                raise ValueError('Expected array end')
            return result
        if lexeme.startswith('"'):
            return json.loads(lexeme)
        if lexeme.startswith("'"):
            return lexeme[1:-1]
        if lexeme in ('true', 'false'):
            return lexeme == 'true'
        return int(lexeme.replace('_', ''))

    result, table = {}, None
    while position < len(lexemes):
        lexeme = take()
        if lexeme == '[':
            table = result
            while True:
                key = take().strip('"\'')
                table = table.setdefault(key, {})
                separator = take()
                if separator == ']':
                    break
                if separator != '.':
                    raise ValueError('Expected table separator')
        else:
            if take() != '=':
                raise ValueError('Expected key = value')
            target = result if table is None else table
            key = lexeme.strip('"\'')
            if key in target:
                raise ValueError('Duplicate TOML key: ' + key)
            target[key] = value()
    return result
