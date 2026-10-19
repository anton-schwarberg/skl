#!/usr/bin/env python3
"""skl – a personal skills library.

Skills are stored centrally in a library (default: ~/.skills-library) and are
NOT active there. Only `skl install` copies them into a project.

Commands:
  skl list [term]                   list skills in the library
  skl show <name>                   description and files of a skill
  skl install <name...> [--to DIR]  copy skill(s) into a folder
                                    (default: ./.claude/skills)
  skl search <term>                 search skills.sh
  skl get <owner/repo@skill>        fetch a skill from GitHub/skills.sh into the library
  skl get <owner/repo> --all        fetch all skills of a repo
  skl save <folder>                 add a local skill folder to the library
  skl remove <name>                 delete a skill from the library
  skl path                          print the library location

Environment variables:
  SKILLS_LIBRARY   alternative library location
  SKILLS_API_URL   alternative search API (default: https://skills.sh)
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

LIB = os.path.expanduser(os.environ.get("SKILLS_LIBRARY", "~/.skills-library"))
API = os.environ.get("SKILLS_API_URL", "https://skills.sh").rstrip("/")
DEFAULT_TARGET = os.path.join(".claude", "skills")
META = ".skl-source"  # records where a skill came from

TTY = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
def c(code, s): return f"\033[{code}m{s}\033[0m" if TTY else s
def bold(s): return c("1", s)
def dim(s): return c("2", s)
def green(s): return c("32", s)
def cyan(s): return c("36", s)
def die(msg): print(c("31", "Error: ") + msg, file=sys.stderr); sys.exit(1)


# ---------- reading SKILL.md ----------
def frontmatter(skill_md):
    """Reads name/description from the YAML frontmatter (no PyYAML needed)."""
    try:
        text = open(skill_md, encoding="utf-8").read()
    except OSError:
        return {}
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    data, key = {}, None
    for line in m.group(1).splitlines():
        kv = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if kv:
            key, val = kv.group(1), kv.group(2).strip()
            if val in (">", "|", ">-", "|-"):
                val = ""
            data[key] = val.strip("'\"")
        elif key and line.startswith((" ", "\t")):
            data[key] = (data[key] + " " + line.strip()).strip()
    return data


def library_skills():
    if not os.path.isdir(LIB):
        return []
    out = []
    for d in sorted(os.listdir(LIB), key=str.lower):
        p = os.path.join(LIB, d)
        md = os.path.join(p, "SKILL.md")
        if os.path.isfile(md):
            fm = frontmatter(md)
            src = ""
            if os.path.isfile(os.path.join(p, META)):
                src = open(os.path.join(p, META)).read().strip()
            out.append({"dir": d, "path": p, "name": fm.get("name", d),
                        "description": fm.get("description", ""), "source": src})
    return out


def find_in_library(name):
    skills = library_skills()
    for s in skills:
        if name in (s["dir"], s["name"]):
            return s
    close = [s["dir"] for s in skills if name.lower() in s["dir"].lower()]
    hint = f" Did you mean: {', '.join(close)}?" if close else " (run skl list to see all)"
    die(f"Skill '{name}' is not in the library.{hint}")


def short(text, n):
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


# ---------- commands ----------
def cmd_list(a):
    skills = library_skills()
    if a.query:
        q = a.query.lower()
        skills = [s for s in skills if q in s["dir"].lower() or q in s["description"].lower()]
    if not skills:
        print(dim(f"No skills found in {LIB}") if not a.query else dim("No matches."))
        if not a.query:
            print("Tip: skl search <term>  or  skl save <folder>")
        return
    width = max(len(s["dir"]) for s in skills)
    cols = shutil.get_terminal_size((100, 20)).columns
    for s in skills:
        desc = short(s["description"], max(20, cols - width - 4))
        print(f"{bold(s['dir'].ljust(width))}  {dim(desc)}")
    print(dim(f"\n{len(skills)} skill(s) in {LIB}"))


def cmd_show(a):
    s = find_in_library(a.name)
    print(bold(s["name"]))
    if s["description"]:
        print(s["description"])
    if s["source"]:
        print(dim("Source: " + s["source"]))
    print(dim("Path:   " + s["path"]))
    print(dim("Files:"))
    for root, _, files in os.walk(s["path"]):
        for f in sorted(files):
            if f == META:
                continue
            print("  " + os.path.relpath(os.path.join(root, f), s["path"]))


def copy_skill(src, dest, force):
    if os.path.exists(dest):
        if not force:
            return False
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(META, ".git"))
    return True


def cmd_install(a):
    target = os.path.abspath(os.path.expanduser(a.to))
    os.makedirs(target, exist_ok=True)
    for name in a.names:
        s = find_in_library(name)
        dest = os.path.join(target, s["dir"])
        if copy_skill(s["path"], dest, a.force):
            print(green("✓ ") + f"{s['dir']} → {dest}")
        else:
            print(c("33", "• ") + f"{s['dir']} already exists in {target} (use --force to overwrite)")


def api_search(query, limit):
    url = f"{API}/api/search?" + urllib.parse.urlencode({"q": query, "limit": limit})
    req = urllib.request.Request(url, headers={"User-Agent": "skl"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
    except Exception as e:
        die(f"Search at {API} failed: {e}")
    res = data.get("skills", [])
    return sorted(res, key=lambda s: s.get("installs") or 0, reverse=True)


def cmd_search(a):
    res = api_search(" ".join(a.query), a.limit)
    if not res:
        print(dim("No matches on skills.sh."))
        return
    have = {s["dir"] for s in library_skills()}
    for s in res:
        name, src = s.get("name", "?"), s.get("source", "")
        installs = s.get("installs") or 0
        mark = green(" ✓ in library") if name in have else ""
        print(f"{bold(name)}  {dim(f'{installs:,} installs')}{mark}")
        print(f"  {cyan(f'skl get {src}@{name}')}")
        print(dim(f"  https://skills.sh/{s.get('id', src + '/' + name)}"))
    print(dim("\nRun the cyan command to add a skill to your library."))


def parse_ref(ref):
    """owner/repo@skill  |  owner/repo  |  https://github.com/owner/repo[...]"""
    ref = ref.strip()
    skill = None
    if "@" in ref and not ref.startswith("git@"):
        ref, skill = ref.rsplit("@", 1)
    m = re.match(r"^(?:https?://github\.com/)?([\w.-]+)/([\w.-]+?)(?:\.git)?(?:/.*)?$", ref)
    if not m:
        die(f"Unknown format: {ref}  (expected owner/repo@skill)")
    return m.group(1), m.group(2), skill


def find_skill_dirs(root):
    out = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in (".git", "node_modules")]
        if "SKILL.md" in fns:
            out.append(dp)
    return out


def cmd_get(a):
    owner, repo, skill = parse_ref(a.ref)
    if not skill and not a.all:
        die("Which skill? Use owner/repo@skill, or --all for every skill in the repo.")
    os.makedirs(LIB, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="skl-")
    try:
        url = f"https://github.com/{owner}/{repo}.git"
        print(dim(f"Fetching {url} …"))
        r = subprocess.run(["git", "clone", "--depth", "1", "-q", url, tmp + "/repo"],
                           capture_output=True, text=True)
        if r.returncode:
            die("git clone failed: " + r.stderr.strip())
        dirs = find_skill_dirs(tmp + "/repo")
        if skill:
            dirs = [d for d in dirs if os.path.basename(d) == skill
                    or frontmatter(os.path.join(d, "SKILL.md")).get("name") == skill]
            if not dirs:
                die(f"No skill '{skill}' found in {owner}/{repo}.")
            dirs = dirs[:1]
        if not dirs:
            die(f"No SKILL.md found in {owner}/{repo}.")
        for d in dirs:
            name = frontmatter(os.path.join(d, "SKILL.md")).get("name") or os.path.basename(d)
            name = re.sub(r"[^\w.-]", "-", name)
            dest = os.path.join(LIB, name)
            if copy_skill(d, dest, a.force):
                with open(os.path.join(dest, META), "w") as f:
                    f.write(f"{owner}/{repo}@{name}\n")
                print(green("✓ ") + f"{name} added to the library")
            else:
                print(c("33", "• ") + f"{name} is already in the library (use --force to update)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def cmd_save(a):
    src = os.path.abspath(os.path.expanduser(a.folder))
    if not os.path.isfile(os.path.join(src, "SKILL.md")):
        die(f"{src} contains no SKILL.md")
    name = a.name or frontmatter(os.path.join(src, "SKILL.md")).get("name") or os.path.basename(src)
    os.makedirs(LIB, exist_ok=True)
    dest = os.path.join(LIB, name)
    if copy_skill(src, dest, a.force):
        with open(os.path.join(dest, META), "w") as f:
            f.write(f"local: {src}\n")
        print(green("✓ ") + f"{name} added to the library")
    else:
        print(c("33", "• ") + f"{name} is already in the library (use --force to overwrite)")


def cmd_remove(a):
    s = find_in_library(a.name)
    if not a.yes:
        if input(f"Delete '{s['dir']}' from the library? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Cancelled.")
            return
    shutil.rmtree(s["path"])
    print(green("✓ ") + f"{s['dir']} removed")


def main():
    p = argparse.ArgumentParser(prog="skl", description="Personal skills library",
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__.split("Commands:")[1])
    sub = p.add_subparsers(dest="cmd", metavar="command")

    s = sub.add_parser("list", aliases=["ls"], help="list skills in the library")
    s.add_argument("query", nargs="?"); s.set_defaults(fn=cmd_list)

    s = sub.add_parser("show", help="show details of a skill")
    s.add_argument("name"); s.set_defaults(fn=cmd_show)

    s = sub.add_parser("install", aliases=["i"], help="copy skill(s) into a folder")
    s.add_argument("names", nargs="+")
    s.add_argument("--to", "-t", default=DEFAULT_TARGET,
                   help=f"target folder (default: ./{DEFAULT_TARGET})")
    s.add_argument("--force", "-f", action="store_true", help="overwrite existing copies")
    s.set_defaults(fn=cmd_install)

    s = sub.add_parser("search", aliases=["s"], help="search skills.sh")
    s.add_argument("query", nargs="+")
    s.add_argument("--limit", "-n", type=int, default=10)
    s.set_defaults(fn=cmd_search)

    s = sub.add_parser("get", help="fetch a skill from GitHub/skills.sh into the library")
    s.add_argument("ref", help="owner/repo@skill")
    s.add_argument("--all", action="store_true", help="fetch every skill in the repo")
    s.add_argument("--force", "-f", action="store_true", help="update existing copies")
    s.set_defaults(fn=cmd_get)

    s = sub.add_parser("save", help="add a local skill folder to the library")
    s.add_argument("folder"); s.add_argument("--name")
    s.add_argument("--force", "-f", action="store_true")
    s.set_defaults(fn=cmd_save)

    s = sub.add_parser("remove", aliases=["rm"], help="delete a skill from the library")
    s.add_argument("name"); s.add_argument("--yes", "-y", action="store_true")
    s.set_defaults(fn=cmd_remove)

    s = sub.add_parser("path", help="print the library location")
    s.set_defaults(fn=lambda a: print(LIB))

    a = p.parse_args()
    if not getattr(a, "fn", None):
        p.print_help(); return
    a.fn(a)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        sys.exit(130)
    except BrokenPipeError:  # e.g. `skl list | head`
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
