import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { resolvePassingNetworkEdgesForFrame } from '../utils/analytics';
import type { PitchAnnotations, FrameData, PassNetworkEdge, PlayerProfile, ShotMarker, SpeedData, TacticalAnnotation } from '../types';

type DrawingMode = 'arrow' | 'circle' | null;
type PitchAnnotationPlacementMode = 'circle' | 'arrow-start' | 'arrow-end' | null;

export type { DrawingMode };

interface TacticalPitchProps {
    frameData: FrameData | null;
    annotations?: PitchAnnotations | null;
    showZones?: boolean;
    showNetwork?: boolean;
    showShots?: boolean;
    showHeatmap?: boolean;
    heatmapData?: number[][] | null;
    passNetwork?: PassNetworkEdge[] | null;
    shotMarkers?: ShotMarker[] | null;
    speedData?: Map<number, SpeedData> | null;
    playerProfiles?: PlayerProfile[];
    onPlayerClick?: (player: PlayerProfile) => void;
    drawingMode?: DrawingMode;
    pitchAnnotationPlacementMode?: PitchAnnotationPlacementMode;
    savedAnnotations?: TacticalAnnotation[];
    onAnnotationCreate?: (x: number, y: number, x2?: number, y2?: number) => void;
}

export default function TacticalPitch({
    frameData,
    annotations,
    showZones = false,
    showNetwork = false,
    showShots = false,
    showHeatmap = false,
    heatmapData = null,
    passNetwork = null,
    shotMarkers = null,
    speedData = null,
    playerProfiles = [],
    onPlayerClick,
    drawingMode = null,
    pitchAnnotationPlacementMode = null,
    savedAnnotations = [],
    onAnnotationCreate,
}: TacticalPitchProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const playerSelectRef = useRef<HTMLSelectElement>(null);
    const previousPlacementModeRef = useRef(pitchAnnotationPlacementMode);
    const placementControlsOwnedFocusRef = useRef(false);
    const descriptionId = useId();
    const [drawStart, setDrawStart] = useState<{ x: number; y: number } | null>(null);
    const [drawCurrent, setDrawCurrent] = useState<{ x: number; y: number } | null>(null);
    const [coordinateX, setCoordinateX] = useState('');
    const [coordinateY, setCoordinateY] = useState('');
    const [coordinateError, setCoordinateError] = useState<string | null>(null);

    const currentFrameProfiles = playerProfiles.filter((profile) => (
        profile.team === 'my_team'
            ? frameData?.My_Team.some((player) => player.id === profile.playerId)
            : frameData?.Enemies.some((player) => player.enemy_id === profile.playerId)
    ));

    useEffect(() => {
        if (
            previousPlacementModeRef.current &&
            !pitchAnnotationPlacementMode &&
            placementControlsOwnedFocusRef.current
        ) {
            (playerSelectRef.current ?? canvasRef.current)?.focus();
        }
        if (!pitchAnnotationPlacementMode) placementControlsOwnedFocusRef.current = false;
        previousPlacementModeRef.current = pitchAnnotationPlacementMode;
    }, [pitchAnnotationPlacementMode]);

    const handleCoordinateSubmit = useCallback((event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        const x = Number(coordinateX);
        const y = Number(coordinateY);
        if (
            coordinateX === '' || coordinateY === '' ||
            !Number.isFinite(x) || !Number.isFinite(y) ||
            x < 0 || x > 100 || y < 0 || y > 100
        ) {
            setCoordinateError('Coordinates must be finite numbers between 0 and 100.');
            return;
        }
        setCoordinateError(null);
        onAnnotationCreate?.(x, y, x, y);
        setCoordinateX('');
        setCoordinateY('');
    }, [coordinateX, coordinateY, onAnnotationCreate]);

    const getCanvasPoint = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
        const canvas = canvasRef.current;
        if (!canvas) return { x: 0, y: 0 };
        const rect = canvas.getBoundingClientRect();
        return {
            x: ((e.clientX - rect.left) / rect.width) * 100,
            y: ((e.clientY - rect.top) / rect.height) * 100,
        };
    }, []);

    const handleMouseDown = useCallback(
        (e: React.MouseEvent<HTMLCanvasElement>) => {
            if (!drawingMode || !onAnnotationCreate) return;
            e.preventDefault();
            setDrawStart(getCanvasPoint(e));
            setDrawCurrent(getCanvasPoint(e));
        },
        [drawingMode, getCanvasPoint, onAnnotationCreate],
    );

    const handleMouseMove = useCallback(
        (e: React.MouseEvent<HTMLCanvasElement>) => {
            if (!drawingMode || !drawStart || !onAnnotationCreate) return;
            setDrawCurrent(getCanvasPoint(e));
        },
        [drawingMode, drawStart, getCanvasPoint, onAnnotationCreate],
    );

    const handleMouseUp = useCallback(
        (e: React.MouseEvent<HTMLCanvasElement>) => {
            if (!drawingMode || !drawStart || !onAnnotationCreate) return;
            e.preventDefault();
            const end = getCanvasPoint(e);
            onAnnotationCreate(drawStart.x, drawStart.y, end.x, end.y);
            setDrawStart(null);
            setDrawCurrent(null);
        },
        [drawingMode, drawStart, getCanvasPoint, onAnnotationCreate],
    );

    // Handle HiDPI canvas scaling
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        const ctx = canvas.getContext('2d');
        if (ctx) {
            ctx.scale(dpr, dpr);
        }
    }, []);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const dpr = window.devicePixelRatio || 1;
        const w = canvas.width / dpr;
        const h = canvas.height / dpr;

        // Clear — pitch green
        ctx.fillStyle = '#166534';
        ctx.fillRect(0, 0, w, h);

        // Pitch lines
        ctx.strokeStyle = 'rgba(255,255,255,0.6)';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(0, 0, w, h);
        ctx.beginPath(); ctx.moveTo(w / 2, 0); ctx.lineTo(w / 2, h); ctx.stroke();
        ctx.beginPath(); ctx.arc(w / 2, h / 2, h * 0.15, 0, Math.PI * 2); ctx.stroke();
        ctx.strokeRect(0, h * 0.2, w * 0.18, h * 0.6);
        ctx.strokeRect(0, h * 0.35, w * 0.06, h * 0.3);
        ctx.strokeRect(w * 0.82, h * 0.2, w * 0.18, h * 0.6);
        ctx.strokeRect(w * 0.94, h * 0.35, w * 0.06, h * 0.3);

        if (!frameData) return;

        const mapX = (pct: number) => (pct / 100) * w;
        const mapY = (pct: number) => (pct / 100) * h;

        // ===== HEAT MAP LAYER =====
        if (showHeatmap && heatmapData) {
            const cols = heatmapData.length;
            const rows = heatmapData[0]?.length || 0;
            const cellW = w / cols;
            const cellH = h / rows;

            for (let c = 0; c < cols; c++) {
                for (let r = 0; r < rows; r++) {
                    const v = heatmapData[c][r];
                    if (v > 0.05) {
                        // Gradient: low=yellow, high=red
                        const hue = 60 - v * 60; // 60=yellow → 0=red
                        const alpha = 0.1 + v * 0.4;
                        ctx.fillStyle = `hsla(${hue}, 100%, 50%, ${alpha})`;
                        ctx.fillRect(c * cellW, r * cellH, cellW, cellH);
                    }
                }
            }
        }

        // ===== ZONE CONTROL =====
        if (showZones) {
            const gridSize = 30; // Reduced from 15 for O(n) improvement
            const playerTeamPositions = frameData.My_Team.map(p => ({ x: p.x, y: p.y }));
            const enemyPositions = frameData.Enemies.map(p => ({ x: p.x, y: p.y }));
            for (let x = 0; x < w; x += gridSize) {
                for (let y = 0; y < h; y += gridSize) {
                    const px = (x / w) * 100;
                    const py = (y / h) * 100;
                    let minTeamDist = Infinity;
                    let minEnemyDist = Infinity;
                    for (const p of playerTeamPositions) {
                        const d = Math.sqrt((px - p.x) ** 2 + (py - p.y) ** 2);
                        if (d < minTeamDist) minTeamDist = d;
                    }
                    for (const p of enemyPositions) {
                        const d = Math.sqrt((px - p.x) ** 2 + (py - p.y) ** 2);
                        if (d < minEnemyDist) minEnemyDist = d;
                    }
                    if (minTeamDist < minEnemyDist && minTeamDist < 35) {
                        ctx.fillStyle = 'rgba(59, 130, 246, 0.15)';
                        ctx.fillRect(x, y, gridSize, gridSize);
                    } else if (minEnemyDist < minTeamDist && minEnemyDist < 35) {
                        ctx.fillStyle = 'rgba(239, 68, 68, 0.15)';
                        ctx.fillRect(x, y, gridSize, gridSize);
                    }
                }
            }
        }

        // ===== PASSING NETWORK =====
        if (showNetwork) {
            for (const edge of resolvePassingNetworkEdgesForFrame(frameData, passNetwork || [])) {
                const thickness = 1 + Math.min(edge.count, 6) * 0.7;
                const opacity = Math.min(0.25 + edge.count * 0.12, 0.85);
                ctx.strokeStyle = `rgba(59, 130, 246, ${opacity})`;
                ctx.lineWidth = thickness;
                ctx.beginPath();
                ctx.moveTo(mapX(edge.from.x), mapY(edge.from.y));
                ctx.lineTo(mapX(edge.to.x), mapY(edge.to.y));
                ctx.stroke();
            }
        }

        if (showShots && shotMarkers) {
            for (const marker of shotMarkers) {
                ctx.fillStyle = marker.team === 'my_team' ? 'rgba(244, 63, 94, 0.88)' : 'rgba(251, 113, 133, 0.78)';
                ctx.strokeStyle = marker.inBox ? '#fde68a' : '#fff';
                ctx.lineWidth = marker.inBox ? 2.5 : 1.5;
                const radius = 4.5 + (marker.xg * 8);
                ctx.beginPath();
                ctx.arc(mapX(marker.x), mapY(marker.y), marker.inBox ? Math.max(radius, 7) : radius, 0, Math.PI * 2);
                ctx.fill();
                ctx.stroke();

                if (marker.xg >= 0.15) {
                    ctx.fillStyle = '#f8fafc';
                    ctx.font = 'bold 9px monospace';
                    ctx.fillText(marker.xg.toFixed(2), mapX(marker.x) + 8, mapY(marker.y) - 8);
                }
            }
        }

        // ===== MY TEAM (Blue) =====
        frameData.My_Team.forEach(p => {
            const isSprinting = speedData?.get(p.id ?? 0)?.isSprinting;

            // Sprint ring
            if (isSprinting) {
                ctx.strokeStyle = '#f97316';
                ctx.lineWidth = 3;
                ctx.beginPath();
                ctx.arc(mapX(p.x), mapY(p.y), 10, 0, Math.PI * 2);
                ctx.stroke();
            }

            ctx.fillStyle = '#3b82f6';
            ctx.beginPath();
            ctx.arc(mapX(p.x), mapY(p.y), 6, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1;
            ctx.stroke();

            // ID label
            if (p.id !== undefined) {
                ctx.fillStyle = '#fff';
                ctx.font = 'bold 9px monospace';
                ctx.fillText(p.id.toString(), mapX(p.x) - 4, mapY(p.y) - 10);
            }

            // Speed label
            const sp = speedData?.get(p.id ?? 0);
            if (sp && sp.speed > 1) {
                ctx.fillStyle = sp.isSprinting ? '#f97316' : '#94a3b8';
                ctx.font = '8px monospace';
                ctx.fillText(`${sp.speed}`, mapX(p.x) + 8, mapY(p.y) + 3);
            }
        });

        // ===== ENEMIES (Red) =====
        frameData.Enemies.forEach(p => {
            ctx.fillStyle = '#ef4444';
            ctx.beginPath();
            ctx.arc(mapX(p.x), mapY(p.y), 6, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1;
            ctx.stroke();

            if (p.enemy_id !== undefined) {
                ctx.fillStyle = '#fff';
                ctx.font = 'bold 9px monospace';
                ctx.fillText(p.enemy_id.toString(), mapX(p.x) - 4, mapY(p.y) - 10);
            }
        });

        // ===== UNASSIGNED PLAYERS =====
        (frameData.unassignedPlayers ?? []).forEach((p) => {
            ctx.fillStyle = '#94a3b8';
            ctx.beginPath();
            ctx.arc(mapX(p.x), mapY(p.y), 6, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#e2e8f0';
            ctx.lineWidth = 1;
            ctx.stroke();

            if (p.id !== undefined) {
                ctx.fillStyle = '#cbd5e1';
                ctx.font = 'bold 9px monospace';
                ctx.fillText(p.id.toString(), mapX(p.x) - 4, mapY(p.y) - 10);
            }
        });

        // ===== BALL =====
        if (frameData.Ball) {
            ctx.fillStyle = '#eab308';
            ctx.beginPath();
            ctx.arc(mapX(frameData.Ball.x), mapY(frameData.Ball.y), 4, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#000';
            ctx.lineWidth = 1;
            ctx.stroke();
        }

        // ===== SAVED ANNOTATIONS =====
        for (const ann of savedAnnotations) {
            if (frameData.Timestamp < ann.timestampStart || frameData.Timestamp > ann.timestampEnd) continue;
            if (ann.type === 'arrow' && ann.x != null && ann.y != null && ann.x2 != null && ann.y2 != null) {
                ctx.strokeStyle = '#f97316';
                ctx.lineWidth = 2.5;
                ctx.beginPath();
                ctx.moveTo(mapX(ann.x), mapY(ann.y));
                ctx.lineTo(mapX(ann.x2), mapY(ann.y2));
                ctx.stroke();
                // Arrowhead
                const angle = Math.atan2(mapY(ann.y2) - mapY(ann.y), mapX(ann.x2) - mapX(ann.x));
                const headLen = 10;
                ctx.fillStyle = '#f97316';
                ctx.beginPath();
                ctx.moveTo(mapX(ann.x2), mapY(ann.y2));
                ctx.lineTo(mapX(ann.x2) - headLen * Math.cos(angle - Math.PI / 6), mapY(ann.y2) - headLen * Math.sin(angle - Math.PI / 6));
                ctx.lineTo(mapX(ann.x2) - headLen * Math.cos(angle + Math.PI / 6), mapY(ann.y2) - headLen * Math.sin(angle + Math.PI / 6));
                ctx.closePath();
                ctx.fill();
            } else if (ann.type === 'circle' && ann.x != null && ann.y != null) {
                ctx.strokeStyle = '#22d3ee';
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.arc(mapX(ann.x), mapY(ann.y), 20, 0, Math.PI * 2);
                ctx.stroke();
                ctx.fillStyle = 'rgba(34, 211, 238, 0.15)';
                ctx.fill();
            }
        }

        // ===== LIVE DRAWING PREVIEW =====
        if (drawingMode === 'circle' && drawStart) {
            ctx.strokeStyle = 'rgba(34, 211, 238, 0.8)';
            ctx.lineWidth = 2;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.arc(mapX(drawStart.x), mapY(drawStart.y), 20, 0, Math.PI * 2);
            ctx.stroke();
            ctx.setLineDash([]);
        } else if (drawingMode === 'arrow' && drawStart && drawCurrent) {
            ctx.strokeStyle = 'rgba(249, 115, 22, 0.8)';
            ctx.lineWidth = 2.5;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.moveTo(mapX(drawStart.x), mapY(drawStart.y));
            ctx.lineTo(mapX(drawCurrent.x), mapY(drawCurrent.y));
            ctx.stroke();
            ctx.setLineDash([]);
            const angle = Math.atan2(mapY(drawCurrent.y) - mapY(drawStart.y), mapX(drawCurrent.x) - mapX(drawStart.x));
            const headLen = 10;
            ctx.fillStyle = 'rgba(249, 115, 22, 0.8)';
            ctx.beginPath();
            ctx.moveTo(mapX(drawCurrent.x), mapY(drawCurrent.y));
            ctx.lineTo(mapX(drawCurrent.x) - headLen * Math.cos(angle - Math.PI / 6), mapY(drawCurrent.y) - headLen * Math.sin(angle - Math.PI / 6));
            ctx.lineTo(mapX(drawCurrent.x) - headLen * Math.cos(angle + Math.PI / 6), mapY(drawCurrent.y) - headLen * Math.sin(angle + Math.PI / 6));
            ctx.closePath();
            ctx.fill();
        }

        // ===== OFFSIDE LINE =====
        if (annotations?.offside_x !== undefined) {
            ctx.strokeStyle = '#ef4444';
            ctx.lineWidth = 2;
            ctx.setLineDash([5, 5]);
            ctx.beginPath();
            const px = mapX(annotations.offside_x as number);
            ctx.moveTo(px, 0);
            ctx.lineTo(px, h);
            ctx.stroke();
            ctx.setLineDash([]);
        }

    }, [frameData, annotations, showZones, showNetwork, showShots, showHeatmap, heatmapData, passNetwork, shotMarkers, speedData, playerProfiles, drawingMode, drawStart, drawCurrent, savedAnnotations]);

    const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
        if (drawingMode || !onPlayerClick || !frameData || playerProfiles.length === 0) return;
        const canvas = canvasRef.current;
        if (!canvas) return;
        const rect = canvas.getBoundingClientRect();
        const clickX = ((e.clientX - rect.left) / rect.width) * 100;
        const clickY = ((e.clientY - rect.top) / rect.height) * 100;

        let closest: PlayerProfile | null = null;
        let closestDist = Infinity;
        for (const profile of currentFrameProfiles) {
            const player = profile.team === 'my_team'
                ? frameData.My_Team.find(player => player.id === profile.playerId)
                : frameData.Enemies.find(player => player.enemy_id === profile.playerId);
            const px = player?.x;
            const py = player?.y;
            if (px === undefined || py === undefined) continue;
            const dist = Math.sqrt((clickX - px) ** 2 + (clickY - py) ** 2);
            if (dist < closestDist && dist < 8) {
                closestDist = dist;
                closest = profile;
            }
        }
        if (closest) onPlayerClick(closest);
    };

    const coordinateLabel = pitchAnnotationPlacementMode === 'circle'
        ? 'Circle'
        : pitchAnnotationPlacementMode === 'arrow-start'
            ? 'Arrow start'
            : 'Arrow end';

    return (
        <div className="relative h-full w-full">
            <canvas
                ref={canvasRef}
                width={900}
                height={600}
                role="img"
                aria-label="Tactical pitch"
                aria-describedby={descriptionId}
                tabIndex={-1}
                className={`w-full h-full object-contain ${drawingMode ? 'cursor-crosshair' : ''}`}
                onClick={handleClick}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={() => { setDrawStart(null); setDrawCurrent(null); }}
            >
                Player and ball positions are drawn on this pitch.
            </canvas>
            <p id={descriptionId} className="sr-only">
                Player and ball positions are drawn on this pitch. Use the current-frame player and coordinate controls to operate it without a pointer.
            </p>

            {(onPlayerClick && currentFrameProfiles.length > 0) || (pitchAnnotationPlacementMode && onAnnotationCreate) ? (
                <div className="absolute bottom-2 left-2 max-w-[calc(100%-1rem)] rounded border border-slate-600 bg-slate-950/90 p-2 text-xs text-slate-200">
                    {onPlayerClick && currentFrameProfiles.length > 0 && (
                        <label className="block">
                            <span className="mb-1 block">Current-frame player</span>
                            <select
                                ref={playerSelectRef}
                                defaultValue=""
                                onChange={(event) => {
                                    const selected = currentFrameProfiles.find(
                                        (profile) => `${profile.team}:${profile.playerId}` === event.currentTarget.value,
                                    );
                                    if (selected) onPlayerClick(selected);
                                }}
                                className="rounded border border-slate-600 bg-slate-900 px-2 py-1"
                            >
                                <option value="">Choose a player</option>
                                {currentFrameProfiles.map((profile) => (
                                    <option key={`${profile.team}:${profile.playerId}`} value={`${profile.team}:${profile.playerId}`}>
                                        {profile.team === 'my_team' ? 'My team' : 'Opponent'} player {profile.playerId}
                                    </option>
                                ))}
                            </select>
                        </label>
                    )}

                    {pitchAnnotationPlacementMode && onAnnotationCreate && (
                        <form
                            onSubmit={handleCoordinateSubmit}
                            onFocusCapture={() => { placementControlsOwnedFocusRef.current = true; }}
                            onBlurCapture={(event) => {
                                if (
                                    event.relatedTarget &&
                                    !event.currentTarget.contains(event.relatedTarget as Node)
                                ) {
                                    placementControlsOwnedFocusRef.current = false;
                                }
                            }}
                            className="mt-2 flex flex-wrap items-end gap-2"
                        >
                            <p className="w-full">Enter pitch coordinates from 0 to 100.</p>
                            <label>
                                <span className="block">{coordinateLabel} X</span>
                                <input
                                    type="number"
                                    min="0"
                                    max="100"
                                    step="any"
                                    required
                                    value={coordinateX}
                                    onChange={(event) => setCoordinateX(event.currentTarget.value)}
                                    className="w-20 rounded border border-slate-600 bg-slate-900 px-2 py-1"
                                />
                            </label>
                            <label>
                                <span className="block">{coordinateLabel} Y</span>
                                <input
                                    type="number"
                                    min="0"
                                    max="100"
                                    step="any"
                                    required
                                    value={coordinateY}
                                    onChange={(event) => setCoordinateY(event.currentTarget.value)}
                                    className="w-20 rounded border border-slate-600 bg-slate-900 px-2 py-1"
                                />
                            </label>
                            <button type="submit" className="rounded border border-slate-500 bg-slate-800 px-2 py-1">
                                {pitchAnnotationPlacementMode === 'circle'
                                    ? 'Place circle'
                                    : pitchAnnotationPlacementMode === 'arrow-start'
                                        ? 'Set arrow start'
                                        : 'Place arrow end'}
                            </button>
                            {coordinateError && <p role="alert" className="w-full text-rose-300">{coordinateError}</p>}
                        </form>
                    )}
                </div>
            ) : null}
        </div>
    );
}
