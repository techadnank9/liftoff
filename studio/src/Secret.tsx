import React from 'react';
import {AbsoluteFill, Easing, interpolate, random, useCurrentFrame, useVideoConfig} from 'remotion';
import {Can, EndCard, INK, P, PANEL, Panel, Y, spring} from './shared';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

// B. "My soda has a secret.": a character goes curious, whispers, gets surprised, then delighted.
export const Secret: React.FC<{hook: string; body: string; endLine: string; endAt: number}> = ({hook, body, endLine, endAt}) => {
	const frame = useCurrentFrame();
	const {height, width, fps} = useVideoConfig();
	const top = height * PANEL;
	if (frame >= endAt) return <EndCard line={endLine} start={endAt} />;

	const s = (t: number) => Math.round(t * fps);
	const whisper = interpolate(frame, [s(1.3), s(1.5), s(2.3), s(2.5)], [0, 1, 1, 0], clamp);
	const surprise = interpolate(frame, [s(2.5), s(2.7)], [0, 1], clamp);
	const delight = interpolate(frame, [s(3.3), s(3.6)], [0, 1], clamp);
	const canPop = spring(frame, s(2.5), 10, 7);
	const shake = surprise > 0 && delight < 1 ? Math.sin(frame * 2.2) * 10 * (1 - delight) : 0;

	// the face: curious (eyes dart, one brow up) -> surprised (wide eyes, O mouth) -> delighted (smile, blush)
	const cx = width / 2 - 120, cy = top + 560, R = 300;
	const look = delight > 0 ? 1 : surprise > 0 ? 1 : Math.sin(frame / 9);
	const eyeR = 46 + surprise * 18 - delight * 10;
	const browL = -18 - surprise * 30 + delight * 10;
	const browR = -40 + Math.sin(frame / 7) * 8 * (1 - surprise) - surprise * 20 + delight * 30;
	const smile = interpolate(delight, [0, 1], [10, 90]);
	const mouthO = surprise * (1 - delight);

	return (
		<AbsoluteFill style={{background: `radial-gradient(circle at 50% 75%, #FFF8B0 0%, ${Y} 70%)`}}>
			{/* hearts once it's delighted */}
			{Array.from({length: 10}).map((_, i) => {
				const st = s(3.5) + i * 4;
				const p = interpolate(frame, [st, st + 40], [0, 1], clamp);
				return (
					<div key={i} style={{position: 'absolute', left: 120 + random(`h${i}`) * (width - 240), top: cy + 200 - p * 520,
						fontSize: 70 + random(`hs${i}`) * 40, opacity: p > 0 ? 1 - p : 0, rotate: `${(random(`hr${i}`) - 0.5) * 40}deg`}}>💗</div>
				);
			})}
			{/* the can pops up from behind */}
			<Can width={260} style={{position: 'absolute', left: cx + R - 40, top: cy - 120 + (1 - canPop) * 520,
				rotate: `${12 - canPop * 12 + Math.sin(frame / 10) * 3}deg`}} />
			{canPop > 0.6 && Array.from({length: 8}).map((_, i) => {
				const a = (i / 8) * Math.PI * 2;
				const p = interpolate(frame, [s(2.75), s(3.2)], [0, 1], clamp);
				return <div key={i} style={{position: 'absolute', left: cx + R + 90 + Math.cos(a) * (60 + p * 160), top: cy - 40 + Math.sin(a) * (60 + p * 160),
					fontSize: 44, opacity: 1 - p}}>✨</div>;
			})}
			<svg width={width} height={height} style={{position: 'absolute', inset: 0, translate: `${shake}px 0px`}}>
				<circle cx={cx} cy={cy} r={R} fill="#FFD84D" stroke={INK} strokeWidth={10} />
				{/* eyes look toward the can when it appears */}
				{[-1, 1].map((side) => (
					<g key={side}>
						<circle cx={cx + side * 105} cy={cy - 60} r={eyeR + 18} fill="white" stroke={INK} strokeWidth={7} />
						<circle cx={cx + side * 105 + look * 16} cy={cy - 60 - surprise * 6} r={eyeR * 0.55} fill={INK} />
						<line x1={cx + side * 105 - 55} x2={cx + side * 105 + 55}
							y1={cy - 150 + (side < 0 ? browL : browR) + side * 8} y2={cy - 150 + (side < 0 ? browL : browR) - side * 8}
							stroke={INK} strokeWidth={14} strokeLinecap="round" />
					</g>
				))}
				{/* blush */}
				<ellipse cx={cx - 175} cy={cy + 60} rx={48} ry={26} fill={P} opacity={0.45 * delight} />
				<ellipse cx={cx + 175} cy={cy + 60} rx={48} ry={26} fill={P} opacity={0.45 * delight} />
				{/* mouth: smirk / O / big smile */}
				{mouthO > 0.5 ? (
					<ellipse cx={cx} cy={cy + 130} rx={50} ry={70} fill={INK} />
				) : (
					<path d={`M${cx - 120} ${cy + 110} Q${cx + 20} ${cy + 110 + smile} ${cx + 120} ${cy + 100 - (1 - delight) * 30}`}
						fill={delight > 0.5 ? INK : 'none'} stroke={INK} strokeWidth={14} strokeLinecap="round" />
				)}
			</svg>
			{/* whisper bubble */}
			<div style={{position: 'absolute', left: cx + 160, top: cy - 300, padding: '26px 38px', background: 'white',
				borderRadius: 48, border: `7px solid ${INK}`, fontFamily: '"Arial Black", Arial', fontSize: 60, color: INK,
				opacity: whisper, scale: String(0.8 + 0.2 * whisper)}}>psst…</div>
			<Panel hook={hook} body={body} />
		</AbsoluteFill>
	);
};
