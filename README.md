# skl – a personal skills library

Skills are stored centrally in `~/.skills-library` and are **not active** there.
Only `skl install` copies a skill into a project (default: `./.claude/skills`).

## Setup (macOS/Linux, requires only python3 and git)

Link the script from this repo instead of copying it, so every change in the
repo takes effect immediately:

```bash
mkdir -p ~/.local/bin
chmod +x ~/Documents/Github/skl/skl.py
ln -sf ~/Documents/Github/skl/skl.py ~/.local/bin/skl
# if ~/.local/bin is not on your PATH yet (zsh):
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

The link is named `skl`, so you type `skl` rather than `skl.py`. If you move or
rename the repo folder, run the `ln -sf` line again with the new path.

Open a new terminal and run `skl list` to check that it works.

## Commands

| Command | What it does |
|---|---|
| `skl list` / `skl list pdf` | list all skills in the library (optionally filtered) |
| `skl show <name>` | description, source and files of a skill |
| `skl install <name> [name…]` | copy into `./.claude/skills/` |
| `skl install <name> --to <folder>` | copy into any folder |
| `skl search <term>` | search skills.sh |
| `skl get owner/repo@skill` | fetch a skill from GitHub into the library |
| `skl get owner/repo --all` | fetch every skill in a repo |
| `skl save <folder>` | add your own skill folder to the library |
| `skl remove <name>` | delete a skill from the library |

`--force` overwrites existing copies for `install`, `get` and `save`
(for example to update a skill inside a project).

## Typical workflow

```bash
skl search changelog              # search skills.sh
skl get anthropics/skills@pdf     # command shown in the search results
skl save ./my-skill               # store your own skill
cd ~/projects/invoices
skl install pdf my-skill          # active only in this project
```

## Where `install` puts skills

`skl install` copies into `.claude/skills/` of the folder you are currently in,
so the skill applies only to that project:

```bash
cd ~/projects/invoices
skl install pdf     # → ~/projects/invoices/.claude/skills/pdf
```

If you use opencode or any other harness, install the skill with

```bash
cd ~/projects/invoices
skl install pdf --to .opencode/skills/    # → ~/projects/invoices/.claude/skills/pdf
```

## Settings
By default, the skills are saved under **~/.skills-library**. If you want to keep the library elsewhere (e.g. in Github, iCloud or Dropbox to sync it), save it under `SKILLS_LIBRARY=/other/path`.

```bash
export SKILLS_LIBRARY=/other/path
echo 'export SKILLS_LIBRARY=/other/path' >> ~/.zshrc
```

`skl path` shows where the library currently lives.
