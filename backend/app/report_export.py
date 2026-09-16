from __future__ import annotations

from datetime import datetime, timezone
from html import escape

from .llm import _build_event_summary
from .schemas import DetectedEvent, FormationSegment, MatchRecord, MatchSummary, ShotAnalytics
from .workbench.reports import assemble_report


def _format_percent(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{round(float(value))}%"


def _format_number(value: float | int | None, digits: int = 1) -> str:
    if value is None:
        return "-"
    if isinstance(value, int):
        return str(value)
    return f"{value:.{digits}f}"


def _availability_lookup(summary: dict, metric: str) -> dict | None:
    for item in summary.get("metricAvailability") or []:
        if item.get("metric") == metric:
            return item
    return None


def _format_available_metric(summary: dict, metric: str, legacy_key: str, digits: int) -> str:
    record = _availability_lookup(summary, metric)
    if record is not None and record.get("availability") not in {"available", "experimental"}:
        return "Unavailable"
    if record is not None and record.get("value") is None and record.get("availability") != "available":
        return "Unavailable"
    value = record.get("value") if record is not None and record.get("value") is not None else summary.get(legacy_key)
    if value is None:
        return "Unavailable"
    return _format_number(value, digits)


def _render_kv_card(label: str, value: str) -> str:
    return (
        '<div class="card stat-card">'
        f'<div class="eyebrow">{escape(label)}</div>'
        f'<div class="metric">{escape(value)}</div>'
        "</div>"
    )


def _render_list_items(items: list[str]) -> str:
    if not items:
        return '<p class="muted">No supporting evidence captured.</p>'
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"


def _collect_data_confidence_notes(summary: dict) -> list[str]:
    notes: list[str] = []
    if summary.get("possession") is None:
        notes.append("Team-controlled possession was not measured; tactical analysis is review-only.")
    ball_signal_status = summary.get("ballSignalStatus")
    if ball_signal_status and ball_signal_status != "trusted":
        notes.append(
            str(summary.get("ballSignalMessage") or "Ball signal is untrusted; possession, xG, and tactical event interpretation are review-only.")
        )
    notes.extend(str(reason) for reason in summary.get("truthGateReasons") or [])
    return notes


def _render_data_confidence_section(summary: dict) -> str:
    notes = _collect_data_confidence_notes(summary)
    if not notes:
        return ""
    return (
        "<section>"
        "<h2>Data Confidence</h2>"
        '<div class="card">'
        '<p class="muted">This report is review-only until the following limitations are resolved.</p>'
        f"{_render_list_items(notes)}"
        "</div>"
        "</section>"
    )


def _render_focus_player(title: str, player: dict | None) -> str:
    if not player:
        return ""
    label = f" • {player['label']}" if player.get("label") else ""
    summary = f'<p class="muted">{escape(player["summary"])}</p>' if player.get("summary") else ""
    return (
        '<div class="card">'
        f'<div class="eyebrow">{escape(title)}</div>'
        f'<h4>#{escape(str(player["trackId"]))} ({escape(player["team"])}){escape(label)}</h4>'
        f"{summary}"
        "</div>"
    )


def render_match_report_html(
    *,
    match_name: str,
    input_mode: str,
    exported_at: str,
    summary: dict,
    formation_timeline: list[dict],
    event_summary: dict,
    tactical_report: dict | None,
    drills: dict | None,
    publication: dict | None = None,
) -> str:
    latest_formations = formation_timeline[-5:]
    publication = publication or {
        "accepted": True,
        "requiresAnalyst": True,
        "wholeMatchFrequency": False,
        "frequencyRequiresDenominator": True,
    }
    whole_match_frequency = "true" if publication.get("wholeMatchFrequency") else "false"
    has_tactical_report = bool(tactical_report)
    has_drills = bool(drills)
    if summary.get("possession") is None:
        has_tactical_report = False
        has_drills = False
        tactical_report = None
        drills = None
    tactical_report = tactical_report or {}
    drills = drills or {}
    player_focus = tactical_report.get("player_focus") or drills.get("player_focus") or {}
    evidence = list(tactical_report.get("evidence") or []) + list(drills.get("evidence") or [])
    event_counts = event_summary.get("eventCounts") or {}
    top_players = event_summary.get("topPlayers") or []
    drill_cards = drills.get("drills") or []
    possession_summary = (
        f"Match controlled {_format_percent(summary['possession'])} possession with "
        if summary.get("possession") is not None
        else "Possession was not measured; "
    )
    fallback_summary = (
        possession_summary +
        f"{_format_available_metric(summary, 'experimental_shot_quality', 'myTeamXg', 2)} experimental shot quality for my team and "
        f"{_format_number(summary.get('enemyXg', 0.0), 2)} experimental shot quality against."
    )

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Guerilla Analytics Report</title>
    <style>
      :root {{
        color-scheme: light;
        --ink: #0f172a;
        --muted: #475569;
        --line: #cbd5e1;
        --panel: #f8fafc;
        --accent: #0f766e;
      }}
      * {{ box-sizing: border-box; }}
      body {{ margin: 0; background: white; color: var(--ink); font-family: "Segoe UI", Arial, sans-serif; }}
      main {{ max-width: 980px; margin: 0 auto; padding: 32px; }}
      header {{ border-bottom: 2px solid var(--line); padding-bottom: 20px; }}
      h1, h2, h3, h4, p {{ margin: 0; }}
      h1 {{ font-size: 30px; }}
      h2 {{ font-size: 18px; margin-bottom: 12px; }}
      h3 {{ font-size: 15px; margin-bottom: 8px; }}
      h4 {{ font-size: 14px; margin-bottom: 6px; }}
      section {{ margin-top: 28px; page-break-inside: avoid; }}
      .eyebrow {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin-bottom: 6px; }}
      .lede {{ margin-top: 10px; line-height: 1.5; color: var(--muted); }}
      .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
      .grid-3 {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
      .card {{ border: 1px solid var(--line); border-radius: 14px; padding: 14px; background: var(--panel); }}
      .stat-card {{ min-height: 88px; }}
      .metric {{ font-size: 28px; font-weight: 700; color: var(--accent); }}
      .muted {{ color: var(--muted); line-height: 1.5; }}
      .report-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
      ul {{ margin: 0; padding-left: 18px; }}
      li {{ margin-top: 6px; line-height: 1.4; }}
      table {{ width: 100%; border-collapse: collapse; }}
      th, td {{ border-bottom: 1px solid var(--line); padding: 8px 0; text-align: left; font-size: 13px; }}
      @media print {{
        main {{ padding: 18px; }}
        .card {{ break-inside: avoid; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <header>
        <div class="eyebrow">Guerilla Analytics Match Report</div>
        <h1>{escape(match_name)}</h1>
        <p class="lede">Input mode: {escape(input_mode)} • Exported at: {escape(exported_at)}</p>
        <p class="lede" data-whole-match-frequency="{whole_match_frequency}">Reviewed passages do not establish a whole-match frequency.</p>
      </header>

      <section>
        <h2>Executive Summary</h2>
        <div class="card">
          <p class="muted">{escape(tactical_report.get("summary") or fallback_summary)}</p>
        </div>
      </section>

      {_render_data_confidence_section(summary)}

      <section>
        <h2>Tactical Analysis</h2>
        {('<div class="report-grid">'
          f'<div class="card"><div class="eyebrow">Attacking</div><p class="muted">{escape(tactical_report.get("attacking", "-"))}</p></div>'
          f'<div class="card"><div class="eyebrow">Defensive</div><p class="muted">{escape(tactical_report.get("defensive", "-"))}</p></div>'
          f'<div class="card"><div class="eyebrow">Pressing</div><p class="muted">{escape(tactical_report.get("pressing", "-"))}</p></div>'
          f'<div class="card"><div class="eyebrow">Weaknesses</div><p class="muted">{escape(tactical_report.get("weaknesses", "-"))}</p></div>'
          '</div>'
          f'<div class="grid" style="margin-top: 12px;">{_render_kv_card("Overall Rating", str(tactical_report.get("rating", "-")) + "/10")}{_render_kv_card("Key Player", "#" + str(tactical_report.get("key_player", "-")))}</div>')
         if has_tactical_report else '<div class="card"><p class="muted">Coach report not generated yet.</p></div>'}
      </section>

      <section>
        <h2>Match Analytics Snapshot</h2>
        <div class="grid-3">
          {_render_kv_card("Possession", _format_percent(summary.get("possession")))}
          {_render_kv_card("My Team experimental shot quality", _format_available_metric(summary, "experimental_shot_quality", "myTeamXg", 2))}
          {_render_kv_card("Enemy experimental shot quality", _format_number(summary.get("enemyXg"), 2))}
          {_render_kv_card("Formation", str(summary.get("formation", "-")))}
          {_render_kv_card("My Team PPDA", _format_available_metric(summary, "my_team_ppda", "myTeamPpda", 1))}
          {_render_kv_card("Enemy PPDA", _format_available_metric(summary, "enemy_ppda", "enemyPpda", 1))}
          {_render_kv_card("My Team Defensive Line", _format_number(summary.get("myTeamDefensiveLineHeight"), 1))}
          {_render_kv_card("Enemy Defensive Line", _format_number(summary.get("enemyDefensiveLineHeight"), 1))}
          {_render_kv_card("My Team High Press Regains", _format_number(summary.get("myTeamHighPressRegains"), 0))}
          {_render_kv_card("Enemy High Press Regains", _format_number(summary.get("enemyHighPressRegains"), 0))}
          {_render_kv_card("My Team Counterpress Recovery", _format_number(summary.get("myTeamCounterpressRecoverySeconds"), 1) + "s")}
          {_render_kv_card("Enemy Counterpress Recovery", _format_number(summary.get("enemyCounterpressRecoverySeconds"), 1) + "s")}
        </div>
      </section>

      <section>
        <h2>Defensive Context</h2>
        <div class="grid-3">
          {_render_kv_card("My Team Block Height", str(summary.get("myTeamBlockHeight", "mid_block").replace("_", " ").title()))}
          {_render_kv_card("Enemy Block Height", str(summary.get("enemyBlockHeight", "mid_block").replace("_", " ").title()))}
          {_render_kv_card("My Team Transition Exposure", _format_number(summary.get("myTeamTransitionExposure"), 2))}
          {_render_kv_card("Enemy Transition Exposure", _format_number(summary.get("enemyTransitionExposure"), 2))}
        </div>
        <h3 style="margin-top: 16px;">Regain Zones</h3>
        <div class="grid-3" style="margin-top: 8px;">
          {_render_kv_card("My Team Defensive Third Regains", _format_number(summary.get("myTeamRegainZones", {}).get("defensive_third", 0), 0))}
          {_render_kv_card("My Team Middle Third Regains", _format_number(summary.get("myTeamRegainZones", {}).get("middle_third", 0), 0))}
          {_render_kv_card("My Team Attacking Third Regains", _format_number(summary.get("myTeamRegainZones", {}).get("attacking_third", 0), 0))}
          {_render_kv_card("Enemy Defensive Third Regains", _format_number(summary.get("enemyRegainZones", {}).get("defensive_third", 0), 0))}
          {_render_kv_card("Enemy Middle Third Regains", _format_number(summary.get("enemyRegainZones", {}).get("middle_third", 0), 0))}
          {_render_kv_card("Enemy Attacking Third Regains", _format_number(summary.get("enemyRegainZones", {}).get("attacking_third", 0), 0))}
        </div>
      </section>

      <section>
        <h2>Formation Phases</h2>
        {('<table><thead><tr><th>Formation</th><th>Start</th><th>End</th></tr></thead><tbody>' +
          ''.join(
            f'<tr><td>{escape(segment.get("formation", "-"))}</td><td>{_format_number(segment.get("startTimestamp"), 1)}s</td><td>{_format_number(segment.get("endTimestamp"), 1)}s</td></tr>'
            for segment in latest_formations
          ) +
          '</tbody></table>')
         if latest_formations else '<div class="card"><p class="muted">No rolling formation segments available.</p></div>'}
      </section>

      <section>
        <h2>Player Focus</h2>
        {('<div class="grid">'
          f'{_render_focus_player("Top Creator", player_focus.get("topCreator"))}'
          f'{_render_focus_player("Top Finisher", player_focus.get("topFinisher"))}'
          f'{_render_focus_player("Top Ball Winner", player_focus.get("topBallWinner"))}'
          + ''.join(_render_focus_player("Other Key Player", player) for player in player_focus.get("otherKeyPlayers", []))
          + '</div>') if player_focus else '<div class="card"><p class="muted">No player-focus highlights stored yet.</p></div>'}
      </section>

      <section>
        <h2>Event Snapshot</h2>
        <div class="grid">
          <div class="card">
            <h3>Event Counts</h3>
            {('<ul>' + ''.join(f'<li>{escape(event_type)}: {escape(str(count))}</li>' for event_type, count in sorted(event_counts.items())) + '</ul>')
             if event_counts else '<p class="muted">No derived event counts available.</p>'}
          </div>
          <div class="card">
            <h3>Top Involvements</h3>
            {('<ul>' + ''.join(
                f'<li>#{escape(str(player.get("trackId")))} ({escape(player.get("team", "-"))}) • {escape(str(player.get("involvements", 0)))} involvements</li>'
                for player in top_players[:5]
              ) + '</ul>')
             if top_players else '<p class="muted">No top-involvement players available.</p>'}
          </div>
        </div>
      </section>

      <section>
        <h2>Training Drills</h2>
        {('<div class="card"><div class="eyebrow">Focus Area</div><p class="muted">' + escape(drills.get("focus_area", "-")) + '</p></div>'
          + '<div class="grid" style="margin-top: 12px;">'
          + ''.join(
              '<div class="card">'
              f'<h3>{escape(drill.get("name", "Drill"))}</h3>'
              f'<p class="muted">{escape(drill.get("objective", "-"))}</p>'
              f'<p class="muted">{escape(drill.get("setup", "-"))}</p>'
              f'<p class="eyebrow">{escape(drill.get("duration", "-"))}</p>'
              '</div>'
              for drill in drill_cards
            )
          + '</div>')
         if drill_cards else '<div class="card"><p class="muted">Training drills not generated yet.</p></div>'}
      </section>

      <section>
        <h2>Evidence</h2>
        <div class="card">
          {_render_list_items(evidence)}
        </div>
      </section>
    </main>
  </body>
</html>"""


def _known_evidence_ids(events: list[DetectedEvent], tactical_report: dict | None, drills: dict | None) -> set[str]:
    known: set[str] = set()
    for event in events:
        payload = event.model_dump(mode="json")
        description = str(payload.get("description") or "").strip()
        if description:
            known.add(description)
        for evidence_id in payload.get("evidenceIds") or []:
            known.add(str(evidence_id))
    del tactical_report, drills
    return known


def build_match_report_export(
    *,
    match: MatchRecord,
    summary: MatchSummary,
    formation_timeline: list[FormationSegment],
    shots: list[ShotAnalytics],
    events: list[DetectedEvent],
    tactical_report: dict | None,
    drills: dict | None,
) -> str:
    event_summary = _build_event_summary(events, shots)
    exported_at = datetime.now(timezone.utc).isoformat()
    claimed = [str(item) for item in (tactical_report or {}).get("evidence") or []]
    assembled = assemble_report(
        metrics=[item.model_dump(mode="json") for item in summary.metricAvailability],
        events=[event.model_dump(mode="json") for event in events],
        claimed_evidence_ids=claimed,
        known_evidence_ids=_known_evidence_ids(events, tactical_report, drills),
        narrative=tactical_report,
    )
    published_tactical = tactical_report if assembled["publication"]["accepted"] else None
    return render_match_report_html(
        match_name=match.name,
        input_mode=match.inputMode,
        exported_at=exported_at,
        summary=summary.model_dump(mode="json"),
        formation_timeline=[segment.model_dump(mode="json") for segment in formation_timeline],
        event_summary=event_summary,
        tactical_report=published_tactical,
        drills=drills,
        publication=assembled["publication"],
    )
