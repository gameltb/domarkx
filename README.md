# Domarkx

**Domarkx** (from **Do**cument + **Mark**down + E**x**ecute): Your documentation is not just static text—it's executable, extensible, and powered by LLMs.

---

## Overview

Domarkx transforms your Markdown documentation and LLM chat logs into powerful, interactive sessions. You remain in full control: your Markdown file is the single source of truth, and every action is a command you define. The workflow is flexible and transparent, allowing you to connect with any command-line tool, script, or executable.

## Key Features

- **🛠️ Your Tools, Your Rules:** Define any command you can imagine using a powerful and intuitive placeholder system.
- **📝 Plain Markdown as Source of Truth:** No proprietary formats. Sessions are just Markdown, portable and editable anywhere.
- **🔍 Transparent Actions, Not Magic:** See exactly what commands will be executed before they run. You're always in control.
- ✂️ **Context-Aware Extraction:** Effortlessly refactor and split your sessions with a clear, auditable text history.

---

## Repository Structure

```
domarkx/
│
├── domarkx.py               # Main Python CLI entry point for document/code block execution
├── pyproject.toml           # Python project configuration & dependencies
├── editors/
│   └── code/
│        ├── README.md       # Extension for VS Code
│        └── package.json    # VS Code extension manifest (adds CodeLens to Markdown)
└── ...
```

- **`domarkx.py`**: The main CLI for executing Markdown-based LLM sessions and code blocks.
- **`editors/code`**: Contains the VS Code extension for integrating Domarkx features (like CodeLenses) in Markdown documents.

---

## Getting Started

### 1. Installation

**Python CLI:**

```bash
# Clone the repository
git clone https://github.com/gameltb/domarkx.git
cd domarkx

# (Optional) Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install .
```

**VS Code Extension (optional):**

1. Open `editors/code` in VS Code.
2. Run `npm install` and `npm run package` to create the `.vsix` file.
3. Install the extension in VS Code using the generated `.vsix`.

---

## How to Use Domarkx

### A. Using the Python CLI

#### Execute an Entire LLM Markdown Session

```bash
python domarkx.py exec-doc <your_markdown_file.md>
```

- This will parse your Markdown LLM conversation file, execute session setup code if present, and interactively run the conversation using an LLM agent.
- All changes and new messages are appended to the Markdown file, preserving history.

#### Execute a Specific Code Block in a Conversation

```bash
python domarkx.py exec-doc-code-block <your_markdown_file.md> <message_index> <code_block_in_message_index>
```

- This executes a specific code block (by message and block index) in your Markdown file.

### B. Using the VS Code Extension

**Domarkx provides a VS Code extension for deeper integration:**

- **CodeLens for Markdown:** Adds "Execute Document" and "Execute Code Block" actions directly above Markdown chat messages and code blocks.
- **Custom Commands:** Configure your own commands for message/code block execution via the extension settings (`Domarkx.executionCommand`, `Domarkx.codeBlockCommands`, etc.).
- **Context Menu & Title Actions:** Quickly run, split, or extract parts of your LLM chat session from the editor interface.

#### Example Configuration

In your VS Code `settings.json`:

```json
{
  "Domarkx.executionCommand": "python domarkx.py exec-doc \"${file}\"",
  "Domarkx.codeBlockCommands": [
    {
      "title": "Run Code Block",
      "command": "python domarkx.py exec-doc-code-block \"${file}\" ${messageIndex} ${codeBlockInMessageIndex}"
    }
  ]
}
```

---

## Example Workflow

1. Write an LLM conversation in Markdown (e.g., with prompts and code snippets).
2. Use the CLI to execute the session and append results to the file.
3. Use VS Code to run or extract messages/code blocks interactively.

---

## Requirements

- **Python ≥ 3.11**
- **VS Code** (for the extension, optional)
- Install Python dependencies via `pip install .` or `pip install -r requirements.txt`.

---

## Contributing

Feel free to open issues or submit PRs for new features, bug fixes, or documentation improvements.

---

## License

MIT License

---

## Contact

Author: gameltb & Gemini

---

## Advanced

- **Custom Agent Models:** You can modify the session setup code in your Markdown to initialize different LLM clients.
- **Extend with Your Own Tools:** Add new commands and integrations in the extension or CLI for your specific workflow.

---

**Domarkx** — Complete your documentation with the results of code execution, powered by LLMs and your own tools.
