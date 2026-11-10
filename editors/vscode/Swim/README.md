# Swim language support for VS Code

Syntax highlighting plus bracket/indentation configuration for `.sw` files.

## Install

Option 1 (development mode):

```bash
cd editors/vscode/Swim
code --extensionDevelopmentPath="$(pwd)"
```

Option 2 (package as a .vsix):

```bash
cd editors/vscode/Swim
npx @vscode/vsce package
code --install-extension Swim-language-0.1.0.vsix
```

You can also copy `syntaxes/Swim.tmLanguage.json` into any editor that supports
TextMate grammars (Sublime Text, TextMate, Zed, etc.).

The generated `.vsix` is a build artifact: it is git-ignored (`*.vsix`), so
never commit or push it. Publish it as a release asset instead if needed.
