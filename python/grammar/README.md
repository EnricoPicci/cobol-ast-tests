# Cobol85 Grammar

## Source

- **Repository:** [antlr/grammars-v4](https://github.com/antlr/grammars-v4)
- **Directory:** `cobol85/`
- **File:** `Cobol85.g4` (combined lexer + parser grammar)
- **Author:** Ulrich Wolffgang (ProLeap)

## Version

Downloaded from the `master` branch on 2026-03-22.

## Local Modifications

None. The grammar is used as-is from the upstream repository.

## Regenerating the Parser

From the `python/` directory:

```bash
pip install -r requirements-build.txt

antlr4 \
    -Dlanguage=Python3 \
    -visitor \
    -listener \
    -o src/cobol_ast/generated \
    grammar/Cobol85.g4
```

ANTLR4 mirrors the input grammar path under the `-o` directory, so the
generated files end up in `src/cobol_ast/generated/grammar/`. This is the
intended layout — import from `cobol_ast.generated.grammar`.

### Troubleshooting: Java not found

`antlr4-tools` is supposed to auto-download a JRE if Java is not installed,
but this does not always work. If the `antlr4` command fails with
"Unable to locate a Java Runtime", install a JDK manually via the
`install-jdk` package (already installed as a dependency of `antlr4-tools`):

```bash
python -c "import jdk; print(jdk.install('11'))"
```

This prints the install path (e.g., `~/.jdk/jdk-11.0.30+7`). On macOS the
`java` binary is inside `Contents/Home/bin/`. Set `JAVA_HOME` before running
`antlr4`:

```bash
export JAVA_HOME=~/.jdk/jdk-11.0.30+7/Contents/Home  # macOS
export JAVA_HOME=~/.jdk/jdk-11.0.30+7                 # Linux
export PATH="$JAVA_HOME/bin:$PATH"
antlr4 ...
```
