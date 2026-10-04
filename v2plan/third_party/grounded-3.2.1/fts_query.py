# Copyright (c) 2025 Andre Rabold
# SPDX-License-Identifier: MIT
# Port of DocumentStore.escapeFtsQuery at f2938c47bb8937c650f0d5ddb614f867773b29f4.
def escape_fts_query(query):
    tokens, current, quoted = [], '', False
    for char in query:
        if char == '"':
            if current:
                tokens.append(current)
                current = ''
            quoted = not quoted
        elif char == ' ' and not quoted:
            if current:
                tokens.append(current)
                current = ''
        else:
            current += char
    if current:
        tokens.append(current)
    quote = lambda text: '"' + text.replace('"', '""') + '"'
    if not tokens:
        return '""'
    if len(tokens) == 1:
        return quote(tokens[0])
    return quote(' '.join(tokens)) + ' OR ' + ' OR '.join(map(quote, tokens))
