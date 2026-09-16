/* eslint-disable react-refresh/only-export-components */
import { useState } from 'react';
import { buildMatchReportExportUrl } from '../utils/api';
import type { ReviewBundleItem, EventTag, FocusPlayer, TacticalReport, DrillResponse } from '../types';
import SaveBundleButton from './SaveBundleButton';
import BundleListPanel from './BundleListPanel';

interface CoachInsightsProps {
  activeTab: 'report' | 'drills';
  llmThinking: boolean;
  matchId: string | null;
  onSwitchMatch?: (matchId: string) => Promise<boolean | void>;
  currentFrame: number;
  events: EventTag[];
  tacticalReport: TacticalReport | null;
  drillResponse: DrillResponse | null;
  ballSignalStatus?: string | null;
  onGenerateReport: () => void;
  onGenerateDrills: () => void;
}

function FocusCard({ title, player, accent }: { title: string; player?: FocusPlayer; accent: string }) {
  if (!player) return null;

  return (
    <div className="p-2 bg-slate-900 rounded border border-slate-700">
      <h4 className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">{title}</h4>
      <div className="mt-1 flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-slate-200">
          #{player.trackId} <span className="text-slate-500">({player.team})</span>
        </span>
        {player.label && <span className={`text-[11px] font-semibold ${accent}`}>{player.label}</span>}
      </div>
      {player.summary && <p className="mt-1 text-xs text-slate-300">{player.summary}</p>}
    </div>
  );
}

function PlayerFocusSection({ playerFocus }: { playerFocus?: TacticalReport['player_focus'] | DrillResponse['player_focus'] }) {
  if (!playerFocus) return null;
  const hasAnyFocus = playerFocus.topCreator || playerFocus.topFinisher || playerFocus.topBallWinner || (playerFocus.otherKeyPlayers?.length ?? 0) > 0;
  if (!hasAnyFocus) return null;

  return (
    <div className="p-2 bg-slate-900 rounded border border-slate-700">
      <h4 className="text-xs font-semibold text-emerald-500 mb-2">Player Focus</h4>
      <div className="grid grid-cols-1 gap-2">
        <FocusCard title="Top Creator" player={playerFocus.topCreator} accent="text-emerald-400" />
        <FocusCard title="Top Finisher" player={playerFocus.topFinisher} accent="text-rose-300" />
        <FocusCard title="Top Ball Winner" player={playerFocus.topBallWinner} accent="text-cyan-300" />
        {playerFocus.otherKeyPlayers && playerFocus.otherKeyPlayers.length > 0 && (
          <div className="p-2 bg-slate-950 rounded border border-slate-700">
            <h5 className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-2">Other Key Players</h5>
            <div className="space-y-1">
              {playerFocus.otherKeyPlayers.map((player) => (
                <p key={`${player.team}-${player.trackId}`} className="text-xs text-slate-300">
                  #{player.trackId} <span className="text-slate-500">({player.team})</span>
                  {player.label ? ` • ${player.label}` : ''}
                  {player.summary ? ` • ${player.summary}` : ''}
                </p>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export interface PlaylistLoadResult {
  success: boolean;
  error?: string;
}

export interface PlaylistLoadOptions {
  currentMatchId: string | null;
  onSwitchMatch?: (matchId: string) => Promise<boolean | void> | boolean | void;
  dispatchEvent?: (event: Event) => boolean;
}

export async function loadPlaylistItemsForMatch(
  items: ReviewBundleItem[],
  { currentMatchId, onSwitchMatch, dispatchEvent = window.dispatchEvent.bind(window) }: PlaylistLoadOptions,
): Promise<PlaylistLoadResult> {
  const matchIds = Array.from(
    new Set(
      items
        .map((item) => item.matchId?.trim())
        .filter((matchId): matchId is string => Boolean(matchId)),
    ),
  );

  if (matchIds.length > 1) {
    return {
      success: false,
      error: 'Playlist contains items from multiple matches. Load a single-match playlist.',
    };
  }

  const targetMatchId = matchIds[0] ?? currentMatchId;
  if (targetMatchId && currentMatchId && targetMatchId !== currentMatchId) {
    if (!onSwitchMatch) {
      return {
        success: false,
        error: 'This playlist belongs to a different match and cannot be loaded here.',
      };
    }
    const switched = await onSwitchMatch(targetMatchId);
    if (switched === false) {
      return {
        success: false,
        error: 'A newer match was selected before this playlist could load.',
      };
    }
  }

  for (const item of items) {
    const customEvent = new CustomEvent('add-event', {
      detail: {
        frame: item.frameStart,
        timestamp: item.timestampStart,
        label: item.label,
        type: 'custom' as const,
      },
    });
    dispatchEvent(customEvent);
  }

  return { success: true };
}

export default function CoachInsights({
  activeTab,
  llmThinking,
  matchId,
  onSwitchMatch,
  currentFrame,
  events,
  tacticalReport,
  drillResponse,
  ballSignalStatus,
  onGenerateReport,
  onGenerateDrills,
}: CoachInsightsProps) {
  const [showBundleList, setShowBundleList] = useState(false);
  const exportHref = matchId ? buildMatchReportExportUrl(matchId) : null;
  const handleLoadPlaylist = async (items: ReviewBundleItem[]) => {
    return loadPlaylistItemsForMatch(items, {
      currentMatchId: matchId,
      onSwitchMatch,
    });
  };

  const getPlaylistItems = (): ReviewBundleItem[] => {
    return events.map((event) => ({
      annotationId: `frame-${event.frame}-${event.type}-${event.timestamp}`,
      matchId: matchId ?? '',
      frameStart: event.frame,
      frameEnd: event.frame,
      timestampStart: event.timestamp,
      timestampEnd: event.timestamp,
      label: event.label,
      description: `Frame ${event.frame} - ${event.type}`,
    }));
  };

  if (activeTab === 'report') {
    return (
      <>
        <div className="grid grid-cols-2 gap-2">
          {ballSignalStatus === 'untrusted' && (
            <div className="col-span-2 flex items-center gap-2 rounded border border-amber-600/60 bg-amber-900/30 px-3 py-2 text-xs text-amber-300">
              <span>⚠️</span>
              <span>Ball signal is untrusted — generated reports may be unreliable.</span>
            </div>
          )}
          <button
            disabled={llmThinking || ballSignalStatus === 'untrusted'}
            onClick={onGenerateReport}
            className="py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded text-xs font-semibold transition text-white"
          >
            {llmThinking ? 'Generating...' : 'Full Report'}
          </button>
          <button
            disabled={!exportHref}
            onClick={() => {
              if (exportHref) {
                window.open(exportHref, '_blank', 'noopener,noreferrer');
              }
            }}
            className="py-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 rounded text-xs font-semibold transition text-emerald-300 border border-slate-700"
          >
            Export HTML
          </button>
          <button
            onClick={() => setShowBundleList(true)}
            className="py-2 bg-blue-900/50 hover:bg-blue-900 rounded text-xs font-semibold transition text-blue-300 border border-blue-700/50"
          >
            Load Playlist
          </button>
          <SaveBundleButton
            currentFrame={currentFrame}
            events={getPlaylistItems()}
          />
        </div>

        {tacticalReport ? (
          <div className="space-y-3">
            <p className="text-[11px] text-amber-200">Reviewed passages do not establish a whole-match frequency.</p>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">Overall Rating</span>
              <span className="text-xl font-bold text-emerald-400">{tacticalReport.rating}/10</span>
            </div>

            {[
              { label: 'Attacking', text: tacticalReport.attacking },
              { label: 'Defensive', text: tacticalReport.defensive },
              { label: 'Pressing', text: tacticalReport.pressing },
              { label: 'Weaknesses', text: tacticalReport.weaknesses },
              { label: 'Summary', text: tacticalReport.summary },
            ].map(({ label, text }) => (
              <div key={label} className="p-2 bg-slate-900 rounded border border-slate-700">
                <h4 className="text-xs font-semibold text-emerald-500 mb-1">{label}</h4>
                <p className="text-xs text-slate-300 leading-relaxed">{text}</p>
              </div>
            ))}

            <div className="p-2 bg-slate-900 rounded border border-emerald-700">
              <span className="text-xs text-slate-400">Key Player: </span>
              <span className="text-xs font-bold text-blue-400">#{tacticalReport.key_player}</span>
            </div>

            <PlayerFocusSection playerFocus={tacticalReport.player_focus} />

            {tacticalReport.event_summary?.eventCounts && Object.keys(tacticalReport.event_summary.eventCounts).length > 0 && (
              <div className="p-2 bg-slate-900 rounded border border-slate-700">
                <h4 className="text-xs font-semibold text-emerald-500 mb-2">Event Snapshot</h4>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(tacticalReport.event_summary.eventCounts).map(([eventType, count]) => (
                    <span key={eventType} className="px-2 py-1 rounded-full border border-slate-600 text-[11px] text-slate-300">
                      {eventType}: {count}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {tacticalReport.event_summary?.topPlayers && tacticalReport.event_summary.topPlayers.length > 0 && (
              <div className="p-2 bg-slate-900 rounded border border-slate-700">
                <h4 className="text-xs font-semibold text-emerald-500 mb-2">Top Involvements</h4>
                <div className="space-y-2">
                  {tacticalReport.event_summary.topPlayers.slice(0, 3).map((player) => (
                    <div key={`${player.team}-${player.trackId}`} className="flex items-center justify-between text-xs text-slate-300">
                      <span>
                        #{player.trackId} <span className="text-slate-500">({player.team})</span>
                      </span>
                      <span className="text-emerald-400">{player.involvements} involvements</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {tacticalReport.evidence && tacticalReport.evidence.length > 0 && (
              <div className="p-2 bg-slate-900 rounded border border-slate-700">
                <h4 className="text-xs font-semibold text-emerald-500 mb-2">Evidence</h4>
                <div className="space-y-1">
                  {tacticalReport.evidence.map((item, index) => (
                    <p key={`${item}-${index}`} className="text-xs text-slate-300 leading-relaxed">
                      {item}
                    </p>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="text-center text-slate-500 text-xs p-6 border border-dashed border-slate-700 rounded">
            Generate a report from the persisted match workspace.
          </div>
        )}
        {showBundleList && (
          <BundleListPanel
            onLoadPlaylist={handleLoadPlaylist}
            onClose={() => setShowBundleList(false)}
          />
        )}
      </>
    );
  }

  return (
    <>
      <div className="grid grid-cols-2 gap-2">
        <button
          disabled={llmThinking || ballSignalStatus === 'untrusted'}
          onClick={onGenerateDrills}
          className="py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded text-xs font-semibold transition text-white"
        >
          {llmThinking ? 'Generating...' : 'Training Drills'}
        </button>
        <button
          disabled={!exportHref}
          onClick={() => {
            if (exportHref) {
              window.open(exportHref, '_blank', 'noopener,noreferrer');
            }
          }}
          className="py-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 rounded text-xs font-semibold transition text-emerald-300 border border-slate-700"
        >
          Export HTML
        </button>
        <button
          onClick={() => setShowBundleList(true)}
          className="py-2 bg-blue-900/50 hover:bg-blue-900 rounded text-xs font-semibold transition text-blue-300 border border-blue-700/50"
        >
          Load Playlist
        </button>
        <SaveBundleButton
          currentFrame={currentFrame}
          events={getPlaylistItems()}
        />
      </div>

      {drillResponse ? (
        <div className="space-y-3">
          <div className="p-2 bg-emerald-900/20 rounded border border-emerald-700">
            <span className="text-xs text-slate-400">Focus Area: </span>
            <span className="text-xs font-semibold text-emerald-400">{drillResponse.focus_area}</span>
          </div>

          <PlayerFocusSection playerFocus={drillResponse.player_focus} />

          {drillResponse.drills.map((drill, index) => (
            <div key={`${drill.name}-${index}`} className="p-3 bg-slate-900 rounded border border-slate-700">
              <div className="flex items-center gap-2 mb-2">
                <span className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-xs">{index + 1}</span>
                <h4 className="text-xs font-semibold text-slate-200">{drill.name}</h4>
                <span className="ml-auto text-xs text-slate-500 font-mono">{drill.duration}</span>
              </div>
              <p className="text-xs text-emerald-400 mb-1">{drill.objective}</p>
              <p className="text-xs text-slate-400 leading-relaxed">{drill.setup}</p>
            </div>
          ))}

          {drillResponse.evidence && drillResponse.evidence.length > 0 && (
            <div className="p-2 bg-slate-900 rounded border border-slate-700">
              <h4 className="text-xs font-semibold text-emerald-500 mb-2">Why These Drills</h4>
              <div className="space-y-1">
                {drillResponse.evidence.map((item, index) => (
                  <p key={`${item}-${index}`} className="text-xs text-slate-300 leading-relaxed">
                    {item}
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="text-center text-slate-500 text-xs p-6 border border-dashed border-slate-700 rounded">
          The backend analysis endpoint can turn stored match state into training ideas.
        </div>
      )}
      {showBundleList && (
        <BundleListPanel
          onLoadPlaylist={handleLoadPlaylist}
          onClose={() => setShowBundleList(false)}
        />
      )}
    </>
  );
}
