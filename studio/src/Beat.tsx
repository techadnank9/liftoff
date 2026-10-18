import React from 'react';
import {AbsoluteFill, Easing, interpolate, random, useCurrentFrame, useVideoConfig} from 'remotion';
import {Can, EndCard, P, PANEL, Panel, Y} from './shared';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

// C. "Pop. Fizz. Repeat.": everything moves on a 120 bpm beat; the can bounces, rings burst, confetti falls.
export const Beat: React.FC<{hook: string; body: string; endLine: string; endAt: number}> = ({hook, body, endLine, endAt}) => {
	const frame = useCurrentFrame();
	const {height, width, fps} = useVideoConfig();
	const top = height * PANEL;
	if (frame >= endAt) return <EndCard line={endLine} start={endAt} />;

	const beat = fps / 2; // 120 bpm
	const k = (frame % beat) / beat;
	const hit = interpolate(k, [0, 0.15, 1], [1, 0.3, 0], {...clamp, easing: Easing.out(Easing.cubic)});
	const bounce = Math.abs(Math.sin(Math.PI * k));
	const shake = hit * 10 * (random(`s${Math.floor(frame / beat)}`) - 0.5);

	return (
		<AbsoluteFill style={{background: Y}}>
			<div style={{position: 'absolute', left: 0, right: 0, top, bottom: 0, overflow: 'hidden',
				background: `radial-gradient(circle at 50% 60%, #ff5fb8 ${10 + hit * 20}%, ${P} 70%)`, translate: `${shake}px ${shake / 2}px`}}>
				{/* burst rings on each beat */}
				{[0, 1, 2].map((r) => {
					const p = ((frame + r * (beat / 3)) % beat) / beat;
					const size = 120 + p * 900;
					return <div key={r} style={{position: 'absolute', left: width / 2 - size / 2, top: 600 - size / 2, width: size, height: size,
						borderRadius: '50%', border: '10px solid rgba(255,242,0,0.7)', opacity: 1 - p}} />;
				})}
				{/* confetti */}
				{Array.from({length: 40}).map((_, i) => {
					const x = random(`cx${i}`) * width;
					const sp = 0.6 + random(`cv${i}`) * 0.8;
					const y = ((random(`cy${i}`) * 1100 + frame * 9 * sp) % 1150) - 60;
					return <div key={i} style={{position: 'absolute', left: x + Math.sin(frame / 8 + i) * 20, top: y, width: 18, height: 34,
						background: i % 3 === 0 ? Y : i % 3 === 1 ? 'white' : '#7ff0ff', rotate: `${frame * 6 + i * 40}deg`, borderRadius: 4}} />;
				})}
				<Can width={330} style={{position: 'absolute', left: width / 2 - 165, top: 230 - bounce * 120,
					rotate: `${Math.sin(frame / beat * Math.PI) * 8}deg`, scale: String(1 + hit * 0.08)}} />
				<div style={{position: 'absolute', left: width / 2 - 140, top: 880, width: 280, height: 40, borderRadius: '50%',
					background: 'rgba(0,0,0,0.25)', scale: String(1 - bounce * 0.4)}} />
			</div>
			<div style={{scale: String(1 + hit * 0.04)}}><Panel hook={hook} body={body} /></div>
		</AbsoluteFill>
	);
};
