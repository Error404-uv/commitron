"""Command-line interface for Commitron."""
import argparse
import getpass
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.text import Text

from . import __version__
from .ai import (AIError, MAX_DIFF_CHUNKS, explain_changes, explain_git_error, generate_messages,
                 split_diff, suggest_branch_name, suggest_logical_commits, summarize_history)
from .git_ops import (GitError, branches, commit, create_branch, current_branch,
                      diff_stat, ensure_repo, files_changed, history, history_entries, staged_diff,
                      status_porcelain, switch_branch, unstaged_diff, repository_root,
                      worktree_changes, stage_paths)
from .safety import find_secret_warnings
from .credentials import (CredentialError, credential_status, set_credential, delete_credential)
from .config import (config_path, load_config, save_config, load_project_convention,
                     save_project_convention, list_profiles, save_profile, use_profile, delete_profile)

console = Console()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="commitron", description="A safer AI-powered Git assistant")
    parser.add_argument("--version", action="version", version=f"Commitron {__version__}")
    sub = parser.add_subparsers(dest="command")

    commit_parser = sub.add_parser("commit", help="Generate a commit message from staged changes")
    commit_parser.add_argument("--dry-run", action="store_true", help="Preview only; never create a commit")
    commit_parser.add_argument("--style", choices=["conventional", "gitmoji", "plain"], default="conventional")
    commit_parser.add_argument("--count", type=int, default=3)
    commit_parser.add_argument("-y", "--yes", action="store_true", help="Skip final commit confirmation")
    commit_parser.add_argument("--allow-secrets", action="store_true", help="Skip the heuristic secret warning")

    auth_parser = sub.add_parser("auth", help="Manage API credentials in the OS keychain")
    auth_sub = auth_parser.add_subparsers(dest="auth_action", required=True)
    auth_set = auth_sub.add_parser("set", help="Save a provider API key in the OS keychain")
    auth_set.add_argument("provider", choices=["gemini", "openai"])
    auth_delete = auth_sub.add_parser("delete", help="Delete a provider API key from the OS keychain")
    auth_delete.add_argument("provider", choices=["gemini", "openai"])
    auth_sub.add_parser("status", help="Show credential availability without revealing secrets")

    sub.add_parser("menu", help="Open the interactive terminal menu")
    sub.add_parser("status", help="Show Git status and current branch")
    sub.add_parser("stage", help="Interactively stage only selected changed paths")
    diff_parser = sub.add_parser("diff", help="Show a Git diff")
    diff_parser.add_argument("--unstaged", action="store_true", help="Show unstaged working-tree changes")
    diff_parser.add_argument("--stat", action="store_true", help="Show a compact change summary")
    explain_parser = sub.add_parser("explain", help="Explain staged changes with the configured AI provider")
    explain_parser.add_argument("--unstaged", action="store_true", help="Explain unstaged working-tree changes instead")
    explain_parser.add_argument("--allow-secrets", action="store_true", help="Skip the heuristic secret warning")
    files_parser = sub.add_parser("files", help="List files changed in the Git index or working tree")
    files_parser.add_argument("--unstaged", action="store_true", help="List unstaged changes")
    config_parser = sub.add_parser("config", help="View or update local Commitron settings")
    config_sub = config_parser.add_subparsers(dest="config_action", required=True)
    config_sub.add_parser("show", help="Show effective configuration (API keys are never stored)")
    config_sub.add_parser("wizard", help="Interactively configure the AI provider")
    profile_parser = config_sub.add_parser("profile", help="Save and switch named provider profiles")
    profile_sub = profile_parser.add_subparsers(dest="profile_action", required=True)
    profile_sub.add_parser("list", help="List saved profiles")
    profile_save = profile_sub.add_parser("save", help="Save current settings as a profile")
    profile_save.add_argument("name")
    profile_use = profile_sub.add_parser("use", help="Apply a saved profile")
    profile_use.add_argument("name")
    profile_delete = profile_sub.add_parser("delete", help="Delete a saved profile")
    profile_delete.add_argument("name")
    set_parser = config_sub.add_parser("set", help="Set provider, model, or base_url")
    set_parser.add_argument("key", choices=["provider", "model", "base_url"])
    set_parser.add_argument("value")
    log_parser = sub.add_parser("history", help="Show recent commits")
    log_parser.add_argument("-n", "--limit", type=int, default=10)
    log_parser.add_argument("--analyze", action="store_true", help="Summarize recent commit history with AI")
    helper_parser = sub.add_parser("git-help", help="Explain a Git error and suggest safe diagnostic steps")
    helper_parser.add_argument("--error", required=True, help="Paste the Git error message")
    helper_parser.add_argument("--context", default="", help="Optional command or situation context")
    branch_parser = sub.add_parser("branch", help="List, create, or switch branches")
    branch_parser.add_argument("action", nargs="?", choices=["create", "switch", "suggest"])
    branch_parser.add_argument("name", nargs="?")
    branch_parser.add_argument("--description", "-d", help="Task description for an AI branch-name suggestion")

    split_parser = sub.add_parser("split", help="Suggest logical commit groups from staged files; does not stage or commit")
    split_parser.add_argument("--style", choices=["conventional", "gitmoji", "plain"], default="conventional")
    split_parser.add_argument("--allow-secrets", action="store_true", help="Skip the heuristic secret warning")

    convention_parser = sub.add_parser("convention", help="Manage repository-specific commit conventions")
    convention_sub = convention_parser.add_subparsers(dest="convention_action", required=True)
    convention_sub.add_parser("show", help="Show the current repository convention")
    convention_set = convention_sub.add_parser("set", help="Save commit-message guidance in .commitron.json")
    convention_set.add_argument("text", help="Project-specific commit-message instructions")
    convention_sub.add_parser("clear", help="Remove the repository-specific commit convention")
    return parser


def _commit_command(args: argparse.Namespace) -> int:
    if not 1 <= args.count <= 5:
        console.print("[red]--count must be between 1 and 5.[/red]")
        return 2
    diff = staged_diff()
    if not diff.strip():
        console.print("[yellow]No staged changes found. Stage only the files you intend to commit, then retry.[/yellow]")
        console.print("[dim]Commitron never runs 'git add .' automatically.[/dim]")
        return 1
    chunk_count = len(split_diff(diff))
    if chunk_count > MAX_DIFF_CHUNKS:
        console.print(Text(
            "Staged diff exceeds the safe processing limit ({} chunks; maximum {}). "
            "No diff content was sent. Split the changes into smaller commits.".format(
                chunk_count, MAX_DIFF_CHUNKS
            ), style="yellow"
        ))
        return 1
    if chunk_count > 1:
        console.print(Text(
            "Large diff: Commitron will analyze all {} chunks in separate AI requests, "
            "then combine their summaries. This may use more provider quota.".format(chunk_count),
            style="yellow"
        ))
        if not Confirm.ask("Send the complete staged diff for analysis?", default=False):
            return 1
    try:
        convention = load_project_convention(Path(repository_root()))
        warnings = find_secret_warnings(diff + "\n" + convention)
        if warnings and not args.allow_secrets:
            console.print(Panel("Possible sensitive content detected: " + ", ".join(warnings), title="Privacy warning", border_style="yellow"))
            console.print("[yellow]The staged diff and project convention may be sent to the configured AI provider.[/yellow]")
            if not Confirm.ask("Send this content anyway?", default=False):
                return 1
        with console.status("[bold green]Generating commit message options..."):
            options = generate_messages(diff, args.count, args.style, convention)
    except AIError as exc:
        console.print(Text("AI error: " + str(exc), style="red"))
        return 1
    console.print(Panel(Text("\n".join("{}. {}".format(i, msg) for i, msg in enumerate(options, 1))), title="Suggested commit messages"))
    if args.yes:
        message = options[0]
    else:
        choices = [str(i) for i in range(1, len(options) + 1)] + ["e", "c"]
        choice = Prompt.ask("Choose a number, e to edit, or c to cancel", choices=choices, default="1")
        if choice == "c":
            console.print("Cancelled.")
            return 0
        message = Prompt.ask("Commit message") if choice == "e" else options[int(choice) - 1]
    if args.dry_run:
        console.print(Panel(Text(message), title="Dry run — no commit created", border_style="blue"))
        return 0
    if not args.yes and not Confirm.ask("Create commit with the selected message?", default=False):
        console.print("Cancelled.")
        return 0
    result = commit(message)
    if result.returncode:
        console.print(Text("Git commit failed: " + (result.stderr.strip() or result.stdout.strip()), style="red"))
        return result.returncode or 1
    console.print("[green]Commit created successfully.[/green]")
    if result.stdout.strip():
        console.print(Text(result.stdout.strip()))
    return 0


def _manage_profiles_menu() -> int:
    """Interactively save, apply, and delete named provider profiles."""
    while True:
        console.print(Panel(Text("Manage provider profiles", style="bold"), title="AI profiles"))
        action = Prompt.ask(
            "Profile action",
            choices=["List", "Save current settings", "Apply profile", "Delete profile", "Back"],
            default="List",
        )
        if action == "Back":
            return 0
        if action == "List":
            profiles = list_profiles()
            if not profiles:
                console.print(Text("No saved profiles."))
            else:
                for name, values in sorted(profiles.items()):
                    endpoint = values["base_url"] or "provider default"
                    console.print(Text("{} — {} / {} ({})".format(
                        name, values["provider"], values["model"] or "default model", endpoint
                    )))
        elif action == "Save current settings":
            name = Prompt.ask("New profile name")
            if name in list_profiles() and not Confirm.ask(
                "Profile '{}' already exists. Overwrite it?".format(name), default=False
            ):
                console.print("Cancelled.")
                continue
            path = save_profile(name)
            console.print(Text("Saved profile '{}' to {}".format(name, path), style="green"))
        elif action == "Apply profile":
            profiles = list_profiles()
            if not profiles:
                console.print("No profiles to apply.")
                continue
            name = Prompt.ask("Profile to apply", choices=sorted(profiles))
            path = use_profile(name)
            console.print(Text("Applied profile '{}' from {}".format(name, path), style="green"))
        else:
            profiles = list_profiles()
            if not profiles:
                console.print("No profiles to delete.")
                continue
            name = Prompt.ask("Profile to delete", choices=sorted(profiles))
            if not Confirm.ask("Delete profile '{}' permanently?".format(name), default=False):
                console.print("Cancelled.")
                continue
            path = delete_profile(name)
            console.print(Text("Deleted profile '{}' from {}".format(name, path), style="green"))


def _interactive_menu() -> int:
    """Run a small keyboard-friendly command menu; actions remain explicit CLI commands."""
    actions = {
        "Status": ["status"],
        "Stage selected files": ["stage"],
        "Review staged diff": ["diff"],
        "Review unstaged diff": ["diff", "--unstaged"],
        "Smart commit": ["commit"],
        "Explain staged changes": ["explain"],
        "Commit history": ["history"],
        "AI settings": ["config", "wizard"],
        "API credentials": ["auth", "status"],
        "Manage AI profiles": "profiles",
        "Exit": None,
    }
    while True:
        console.print(Panel(Text("Choose a Git workflow or settings task", style="bold"), title="Commitron"))
        choice = Prompt.ask("Action", choices=list(actions), default="Status")
        command = actions[choice]
        if command is None:
            console.print("Goodbye.")
            return 0
        if command == "profiles":
            result = _manage_profiles_menu()
        else:
            result = main(command)
        if result not in (0,):
            console.print(Text("Action exited with status {}.".format(result), style="yellow"))
        if not Confirm.ask("Return to the menu?", default=True):
            return 0


def main(argv=None) -> int:
    parser = _parser()
    raw_args = list(sys.argv[1:] if argv is None else argv)
    known_commands = {"auth", "menu", "commit", "status", "stage", "diff", "history", "branch", "explain", "files", "config", "split", "convention", "git-help"}
    # Keep the original convenient default: options without a subcommand mean `commit`.
    if not raw_args:
        raw_args = ["commit"]
    elif raw_args[0] not in known_commands and raw_args[0] not in {"-h", "--help", "--version"}:
        raw_args.insert(0, "commit")
    args = parser.parse_args(raw_args)
    command = args.command or "commit"
    try:
        if command == "menu":
            return _interactive_menu()
        if command == "auth":
            if args.auth_action == "status":
                for provider in ("gemini", "openai", "ollama"):
                    console.print(Text("{}: {}".format(provider, credential_status(provider))))
            elif args.auth_action == "set":
                if not sys.stdin.isatty():
                    raise CredentialError("Run 'commitron auth set' from an interactive terminal so the API key is not echoed.")
                secret = getpass.getpass("{} API key (input hidden): ".format(args.provider.title()))
                set_credential(args.provider, secret)
                console.print(Text("{} credential saved to the OS keychain.".format(args.provider.title()), style="green"))
            else:
                if not Confirm.ask("Delete the saved {} credential from the OS keychain?".format(args.provider.title()), default=False):
                    console.print("Cancelled.")
                    return 0
                removed = delete_credential(args.provider)
                console.print(Text("Credential deleted." if removed else "No saved credential was found."))
            return 0
        if command == "config":
            if args.config_action == "show":
                config = load_config()
                config_text = "\n".join("{}: {}".format(k, v or "(provider default)") for k, v in config.items()) + "\nConfig file: " + str(config_path())
                console.print(Panel(Text(config_text), title="Commitron configuration"))
            elif args.config_action == "set":
                path = save_config({args.key: args.value})
                console.print(Text("Saved {} to {}".format(args.key, path), style="green"))
            elif args.config_action == "wizard":
                current = load_config()
                provider = Prompt.ask("AI provider", choices=["gemini", "openai", "ollama"], default=current["provider"])
                model = Prompt.ask("Model (blank = provider default)", default=current["model"])
                base_url = Prompt.ask("Custom base URL (blank = provider default)", default=current["base_url"])
                path = save_config({"provider": provider, "model": model, "base_url": base_url})
                console.print(Text("Configuration saved to {}. API keys are not stored in config; use environment variables or the optional OS keychain.".format(path), style="green"))
            else:
                action = args.profile_action
                if action == "list":
                    profiles = list_profiles()
                    if not profiles:
                        console.print(Text("No saved profiles."))
                    else:
                        for name, values in sorted(profiles.items()):
                            console.print(Text("{} — {} / {}".format(name, values["provider"], values["model"] or "default model")))
                elif action == "save":
                    path = save_profile(args.name)
                    console.print(Text("Saved profile '{}' to {}".format(args.name, path), style="green"))
                elif action == "use":
                    path = use_profile(args.name)
                    console.print(Text("Applied profile '{}' from {}".format(args.name, path), style="green"))
                else:
                    if not Confirm.ask("Delete profile '{}' permanently?".format(args.name), default=False):
                        console.print("Cancelled.")
                        return 0
                    path = delete_profile(args.name)
                    console.print(Text("Deleted profile '{}' from {}".format(args.name, path), style="green"))
            return 0
        if command == "convention":
            ensure_repo()
            root = Path(repository_root())
            if args.convention_action == "show":
                value = load_project_convention(root)
                console.print(Text(value or "No repository-specific convention is configured."))
            elif args.convention_action == "set":
                path = save_project_convention(root, args.text)
                console.print(Text("Saved repository commit convention to {}".format(path), style="green"))
            else:
                path = save_project_convention(root, "")
                console.print(Text("Removed repository-specific commit convention from {}".format(path), style="green"))
            return 0
        ensure_repo()
        if command == "commit":
            return _commit_command(args)
        if command == "stage":
            changes = worktree_changes()
            if not changes:
                console.print(Text("Working tree is clean; there are no paths to stage."))
                return 0
            console.print(Panel(Text("Select only the paths you want in the next commit."), title="Interactive staging"))
            for index, item in enumerate(changes, 1):
                console.print(Text("{}. [{}] {}".format(index, item["status"], item["path"])))
            raw_selection = Prompt.ask("Enter comma-separated numbers, or c to cancel", default="c").strip()
            if raw_selection.lower() == "c":
                console.print("Cancelled. The Git index was not changed.")
                return 0
            try:
                selected_numbers = [int(part.strip()) for part in raw_selection.split(",")]
            except ValueError:
                console.print(Text("Invalid selection. Use comma-separated file numbers.", style="red"))
                return 2
            if not selected_numbers or len(set(selected_numbers)) != len(selected_numbers) or any(
                number < 1 or number > len(changes) for number in selected_numbers
            ):
                console.print(Text("Selection contains duplicate or out-of-range numbers.", style="red"))
                return 2
            selected = [changes[number - 1] for number in selected_numbers]
            console.print(Panel(Text("\n".join("[{}] {}".format(item["status"], item["path"]) for item in selected)), title="Paths to stage"))
            if not Confirm.ask("Stage exactly these {} path(s)?".format(len(selected)), default=False):
                console.print("Cancelled. The Git index was not changed.")
                return 0
            stage_paths([item["path"] for item in selected])
            console.print(Text("Staged {} selected path(s).".format(len(selected)), style="green"))
        elif command == "status":
            console.print(Text("Branch: " + current_branch(), style="bold"))
            console.print(Text(status_porcelain() or "Working tree clean"))
        elif command == "diff":
            if args.stat:
                output = diff_stat(staged=not args.unstaged)
            else:
                output = unstaged_diff() if args.unstaged else staged_diff()
            console.print(Text(output or "No matching diff."))
        elif command == "files":
            names = files_changed(staged=not args.unstaged)
            console.print(Text("\n".join(names) if names else "No changed tracked files."))
        elif command == "explain":
            diff = unstaged_diff() if args.unstaged else staged_diff()
            if not diff.strip():
                console.print("[yellow]No matching changes found.[/yellow]")
                return 1
            chunk_count = len(split_diff(diff))
            if chunk_count > MAX_DIFF_CHUNKS:
                console.print(Text(
                    "Diff exceeds the safe processing limit ({} chunks; maximum {}). "
                    "No diff content was sent. Narrow the changes and retry.".format(
                        chunk_count, MAX_DIFF_CHUNKS
                    ), style="yellow"
                ))
                return 1
            if chunk_count > 1:
                console.print(Text(
                    "Large diff: all {} chunks will be sent in separate AI requests; "
                    "this may use more provider quota.".format(chunk_count), style="yellow"
                ))
                if not Confirm.ask("Send the complete diff for analysis?", default=False):
                    return 1
            warnings = find_secret_warnings(diff)
            if warnings and not args.allow_secrets:
                console.print(Panel("Possible sensitive content detected: " + ", ".join(warnings), title="Privacy warning", border_style="yellow"))
                console.print("[yellow]This diff may be sent to the configured AI provider.[/yellow]")
                if not Confirm.ask("Send this diff anyway?", default=False):
                    return 1
            with console.status("[bold green]Analyzing changes..."):
                explanation = explain_changes(diff)
            console.print(Panel(Text(explanation), title="Change explanation"))
        elif command == "history":
            if not 1 <= args.limit <= 100:
                parser.error("history --limit must be between 1 and 100")
            if args.analyze:
                entries = history_entries(args.limit)
                if not entries:
                    console.print(Text("No commits found."))
                    return 0
                payload = "\n".join(
                    "{} {} {}\n{}".format(item["hash"][:12], item["date"], item["subject"], item["body"])
                    for item in entries
                )
                warnings = find_secret_warnings(payload)
                if warnings:
                    console.print(Panel("Possible sensitive content detected: " + ", ".join(warnings), title="Privacy warning", border_style="yellow"))
                console.print(Text("Commit subjects and bodies will be sent to the configured AI provider."))
                if not Confirm.ask("Send the last {} commit records for analysis?".format(len(entries)), default=False):
                    console.print("Cancelled. No data was sent.")
                    return 0
                with console.status("[bold green]Analyzing commit history..."):
                    analysis = summarize_history(entries)
                console.print(Panel(Text(analysis), title="Commit history analysis"))
            else:
                console.print(Text(history(args.limit) or "No commits found."))
        elif command == "git-help":
            warnings = find_secret_warnings(args.error + "\n" + args.context)
            if warnings:
                console.print(Panel("Possible sensitive content detected: " + ", ".join(warnings), title="Privacy warning", border_style="yellow"))
            console.print(Text("The supplied error and context will be sent to the configured AI provider."))
            if not Confirm.ask("Send this Git error for explanation?", default=False):
                console.print("Cancelled. No data was sent.")
                return 0
            with console.status("[bold green]Explaining Git error..."):
                explanation = explain_git_error(args.error, args.context)
            console.print(Panel(Text(explanation), title="Git error explanation"))
        elif command == "branch":
            if args.action is None:
                console.print(Text(branches() or "No branches found."))
            elif args.action == "suggest":
                if not args.description:
                    parser.error("branch suggest requires --description")
                existing = branches().splitlines()
                if not Confirm.ask("Send the task description and existing branch names to the configured AI provider?", default=False):
                    console.print("Cancelled. No data was sent.")
                    return 0
                branch_context = args.description + "\n" + "\n".join(existing)
                warnings = find_secret_warnings(branch_context)
                if warnings:
                    console.print(Panel("Possible sensitive content detected: " + ", ".join(warnings), title="Privacy warning", border_style="yellow"))
                    if not Confirm.ask("Send this information anyway?", default=False):
                        return 1
                with console.status("[bold green]Generating branch-name suggestion..."):
                    suggestion = suggest_branch_name(args.description, existing)
                console.print(Panel(Text(suggestion), title="Suggested branch name"))
                console.print(Text("Suggestion only: no branch was created. Review it before using it.", style="dim"))
            elif not args.name:
                parser.error("branch create/switch requires a branch name")
            elif args.action == "create":
                create_branch(args.name)
                console.print(Text("Created and switched to " + args.name, style="green"))
            else:
                switch_branch(args.name)
                console.print(Text("Switched to " + args.name, style="green"))
        elif command == "split":
            diff = staged_diff()
            changed = files_changed(staged=True)
            if len(changed) < 2 or not diff.strip():
                console.print(Text("Stage changes in at least two tracked files to request file-level logical commit suggestions.", style="yellow"))
                return 1
            chunk_count = len(split_diff(diff))
            if chunk_count > MAX_DIFF_CHUNKS:
                console.print(Text("Staged diff exceeds the safe processing limit. No diff content was sent.", style="yellow"))
                return 1
            if chunk_count > 1:
                console.print(Text("Large diff: all {} chunks will be analyzed; this may use more provider quota.".format(chunk_count), style="yellow"))
                if not Confirm.ask("Send the complete staged diff for logical grouping?", default=False):
                    return 1
            convention = load_project_convention(Path(repository_root()))
            warnings = find_secret_warnings(diff + "\n" + convention)
            if warnings and not args.allow_secrets:
                console.print(Panel("Possible sensitive content detected: " + ", ".join(warnings), title="Privacy warning", border_style="yellow"))
                console.print("[yellow]The staged diff and project convention may be sent to the configured AI provider.[/yellow]")
                if not Confirm.ask("Send this content anyway?", default=False):
                    return 1
            try:
                with console.status("[bold green]Analyzing staged files for logical commit groups..."):
                    groups = suggest_logical_commits(diff, changed, args.style, convention)
            except AIError as exc:
                console.print(Text("AI error: " + str(exc), style="red"))
                return 1
            for index, group in enumerate(groups, 1):
                console.print(Panel(
                    Text("Message: {}\nReason: {}\nFiles:\n{}".format(
                        group["message"], group["reason"],
                        "\n".join("  - " + item for item in group["files"])
                    )), title="Suggested logical commit {}".format(index)
                ))
            console.print(Text("Suggestions only: no files were staged, unstaged, or committed. Review the groups and perform any staging manually.", style="yellow"))
        return 0
    except GitError as exc:
        console.print(Text("Git error: " + str(exc), style="red"))
        return 1
    except (AIError, CredentialError, ValueError) as exc:
        console.print(Text("Error: " + str(exc), style="red"))
        return 1
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        return 130
    except EOFError:
        console.print("\n[yellow]Input closed; no further action was taken.[/yellow]")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
