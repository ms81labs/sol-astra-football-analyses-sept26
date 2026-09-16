"""CLI entrypoint for research-addon.

This module exposes the addon command-line interface for:
- Path resolution and auditing
- Track listing
- Experiment execution

All paths are resolved to addon-owned or temp roots only.
No writes to core product paths (backend/, frontend/, etc.) are allowed.
"""
import argparse
import sys

from research_addon.path_guards import PathResolutionError, get_default_run_root, resolve_run_root


def _add_judge_context_arguments(parser):
    """Register the explicit inputs shared by readiness and execution."""
    parser.add_argument("--manifest", default=None, help="Explicit corpus manifest")
    parser.add_argument("--repo-root", default=None, help="Football-analyst repository")
    parser.add_argument("--python", default=None, help="Python interpreter for the delegate")
    parser.add_argument("--entry-index", default="0", help="Zero-based manifest entry")


def cmd_paths_resolve(args):
    """Resolve and report storage paths."""
    storage_root = args.storage_root

    try:
        resolved = resolve_run_root(storage_root=storage_root)
        print(f"Resolved storage root: {resolved}")
        print(f"Default run root: {get_default_run_root()}")

        print("Status: SAFE - using validated root")

        return 0
    except PathResolutionError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def cmd_paths(args):
    """Path management commands."""
    if args.subcommand == "resolve":
        return cmd_paths_resolve(args)
    else:
        print(f"Unknown path subcommand: {args.subcommand}", file=sys.stderr)
        return 1


def cmd_corpus_show(args):
    """Show corpus manifest contents."""
    from research_addon.corpus import CorpusManifest

    manifest_path = args.manifest if args.manifest else None
    if manifest_path:
        try:
            manifest = CorpusManifest.from_file(manifest_path)
        except FileNotFoundError:
            print(f"ERROR: Manifest not found: {manifest_path}", file=sys.stderr)
            return 1
    else:
        manifest = CorpusManifest.create_with_default_entries()

    print(f"Corpus manifest: {manifest.manifest_path}")
    print(f"Fingerprint: {manifest.fingerprint}")
    print(f"Entries: {len(manifest)}")
    print()
    for i, entry in enumerate(manifest.entries):
        print(f"  [{i}] {entry.get('video_id', '?')}")
        print(f"      video_path: {entry.get('video_path', '?')}")
        print(f"      ground_truth_path: {entry.get('ground_truth_path', '?')}")
        print(f"      tags: {entry.get('tags', [])}")
        print()
    return 0


def cmd_corpus(args):
    """Corpus manifest commands."""
    if args.subcommand == "show":
        return cmd_corpus_show(args)
    else:
        print(f"Unknown corpus subcommand: {args.subcommand}", file=sys.stderr)
        return 1


def cmd_judge(args):
    """Judge wrapper commands for supported-coverage lane."""
    if args.subcommand not in ("supported-coverage",):
        print(f"Unknown judge subcommand: {args.subcommand}", file=sys.stderr)
        print("Supported tracks: supported-coverage", file=sys.stderr)
        return 1

    from research_addon.judge import JudgeExecutionError, run_judge

    try:
        result = run_judge(
            manifest_path=args.manifest,
            storage_root=args.storage_root,
            repo_root=args.repo_root,
            python=args.python,
            entry_index=args.entry_index,
            dry_run=args.dry_run,
        )
        # Pretty-print JSON output
        import json
        print(json.dumps(result, indent=2, default=str))
        return 0
    except (JudgeExecutionError, PathResolutionError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return getattr(exc, "exit_code", 1)


def cmd_tracks_list(args):
    """List available tracks."""
    from research_addon.judge import judge_is_ready

    status = (
        "executable-now"
        if judge_is_ready(
            args.manifest,
            repo_root=args.repo_root,
            python=args.python,
            entry_index=args.entry_index,
        )
        else "available-with-config"
    )
    print("Available tracks:")
    print(f"  supported-coverage  [{status}]  Active research track")
    print("")
    print("Planned tracks (not executable):")
    print("  possession/events    [planned]     Future track")
    print("  trust-crops          [planned]     Future track")
    print("  gpu-bounded-loops    [planned]     Future track")
    print("  later-training       [planned]     Future track")
    return 0


def cmd_tracks(args):
    """Track management commands."""
    if args.subcommand == "list":
        return cmd_tracks_list(args)
    else:
        print(f"Unknown tracks subcommand: {args.subcommand}", file=sys.stderr)
        return 1


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="research_addon",
        description="Isolated autoresearch addon for supported-coverage experiments"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # paths command
    paths_parser = subparsers.add_parser("paths", help="Path resolution and auditing")
    paths_subparsers = paths_parser.add_subparsers(dest="subcommand", help="Path subcommand")

    paths_resolve_parser = paths_subparsers.add_parser("resolve", help="Resolve storage paths")
    paths_resolve_parser.add_argument(
        "--storage-root",
        help="Override storage root (addon or validated temporary directory)"
    )
    paths_resolve_parser.set_defaults(func=cmd_paths)

    # tracks command
    tracks_parser = subparsers.add_parser("tracks", help="Track management")
    tracks_subparsers = tracks_parser.add_subparsers(dest="subcommand", help="Track subcommand")

    tracks_list_parser = tracks_subparsers.add_parser("list", help="List available tracks")
    _add_judge_context_arguments(tracks_list_parser)
    tracks_list_parser.set_defaults(func=cmd_tracks)

    # corpus command
    corpus_parser = subparsers.add_parser("corpus", help="Corpus manifest management")
    corpus_subparsers = corpus_parser.add_subparsers(dest="subcommand", help="Corpus subcommand")

    corpus_show_parser = corpus_subparsers.add_parser("show", help="Show corpus manifest")
    corpus_show_parser.add_argument(
        "--manifest",
        default=None,
        help="Path to manifest file (default: addon default)"
    )
    corpus_show_parser.set_defaults(func=cmd_corpus)

    # judge command
    judge_parser = subparsers.add_parser("judge", help="Judge wrapper commands")
    judge_subparsers = judge_parser.add_subparsers(dest="subcommand", help="Judge subcommand")

    judge_supported_parser = judge_subparsers.add_parser("supported-coverage", help="Run supported-coverage judge")
    judge_supported_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show contract info without running proof"
    )
    judge_supported_parser.add_argument(
        "--storage-root",
        default=None,
        help="Storage root override"
    )
    _add_judge_context_arguments(judge_supported_parser)
    judge_supported_parser.set_defaults(func=cmd_judge)

    # Set default function for paths and tracks parsers
    paths_parser.set_defaults(func=cmd_paths)
    tracks_parser.set_defaults(func=cmd_tracks)
    corpus_parser.set_defaults(func=cmd_corpus)
    judge_parser.set_defaults(func=cmd_judge)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
