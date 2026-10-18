import React from 'react';
import {AbsoluteFill, Easing, interpolate, random, useCurrentFrame, useVideoConfig} from 'remotion';
import {Bubbles, Can, EndCard, P, PANEL, Panel, Y, spring} from './shared';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

// A. "Ever seen soda born?": a glass draws itself, poppi pours in, fruit drops, the can arrives.
export const Process: React.FC<{hook: string; body: string; endLine: string; endAt: number}> = ({hook, body, endLine, endAt}) => {
	const frame = useCurrentFrame();
	const {height, width, fps} = useVideoConfig();
	const top = height * PANEL;
	if (frame >= endAt) return <EndCard line={endLine} start={endAt} />;

	const draw = interpolate(frame, [0, 0.9 * fps], [1, 0], {...clamp, easing: Easing.bezier(0.6, 0, 0.2, 1)});
	const pour = interpolate(frame, [0.6 * fps, 1.0 * fps, 4.2 * fps, 4.6 * fps], [0, 1, 1, 0], clamp);
	const fill = interpolate(frame, [0.9 * fps, 4.8 * fps], [0, 1], {...clamp, easing: Easing.bezier(0.3, 0, 0.3, 1)});
	const canIn = spring(frame, Math.round(3.6 * fps), 14, 10);

	const gx = width / 2 - 170, gy = top + 230, gw = 340, gh = 560; // the glass
	const level = gy + gh - fill * (gh - 60);
	const wave = Array.from({length: 21}).map((_, i) => {
		const x = gx + 18 + (i / 20) * (gw - 36);
		return `${x},${level + Math.sin(frame / 5 + i / 2) * 9}`;
	}).join(' ');

	return (
		<AbsoluteFill style={{background: `linear-gradient(180deg, ${Y} 0%, #FFF8A0 55%, #FFE8F4 100%)`}}>
			{/* pour stream */}
			<div style={{position: 'absolute', left: width / 2 - 22, top, width: 44, height: Math.max(0, level - top) * pour,
				background: `linear-gradient(90deg, #ff4fb0, ${P}, #b80070)`, borderRadius: 22, opacity: pour}} />
			<svg width={width} height={height} style={{position: 'absolute', inset: 0}}>
				<defs><clipPath id="glass"><path d={`M${gx + 14} ${gy} L${gx + 34} ${gy + gh} L${gx + gw - 34} ${gy + gh} L${gx + gw - 14} ${gy} Z`} /></clipPath></defs>
				<g clipPath="url(#glass)">
					<polygon points={`${gx},${gy + gh} ${wave} ${gx + gw},${gy + gh}`} fill={P} opacity={0.92} />
					<rect x={gx} y={level} width={gw} height={gh} fill="url(#none)" />
				</g>
				<path d={`M${gx + 14} ${gy} L${gx + 34} ${gy + gh} L${gx + gw - 34} ${gy + gh} L${gx + gw - 14} ${gy}`}
					fill="none" stroke="white" strokeWidth={12} strokeLinejoin="round" pathLength={1}
					strokeDasharray="1 1" strokeDashoffset={draw} />
				{/* fruit falls and splashes */}
				{[{e: '🍓', t: 1.6, x: -60}, {e: '🍋', t: 2.3, x: 50}, {e: '🍓', t: 3.0, x: 0}].map((f, i) => {
					const p = interpolate(frame, [f.t * fps, f.t * fps + 18], [0, 1], {...clamp, easing: Easing.in(Easing.quad)});
					const y = interpolate(p, [0, 1], [top - 120, level - 20]);
					const ring = interpolate(frame, [f.t * fps + 18, f.t * fps + 34], [0, 1], clamp);
					return (
						<g key={i}>
							<text x={width / 2 + f.x} y={y} fontSize={110} textAnchor="middle" opacity={p > 0 && ring < 1 ? 1 : 0}>{f.e}</text>
							<ellipse cx={width / 2 + f.x} cy={level} rx={40 + ring * 120} ry={10 + ring * 22} fill="none"
								stroke="white" strokeWidth={6} opacity={ring > 0 ? 1 - ring : 0} />
						</g>
					);
				})}
			</svg>
			<div style={{position: 'absolute', inset: 0, clipPath: `inset(${level}px ${gx + 30}px 0 ${gx + 30}px)`}}>
				<Bubbles seed="glass" n={26} top={level} bottom={gy + gh} speed={1.6} />
			</div>
			<Can width={250} style={{position: 'absolute', left: width - 330 + (1 - canIn) * 400, top: top + 520,
				rotate: `${(1 - canIn) * 25 + Math.sin(frame / 14) * 3}deg`, opacity: canIn}} />
			<Panel hook={hook} body={body} />
		</AbsoluteFill>
	);
};
