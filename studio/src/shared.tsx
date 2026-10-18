import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, random, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

// poppi, from its own website (assets/drinkpoppi-com/brand.json)
export const Y = '#FFF200';
export const P = '#EC008C';
export const INK = '#141414';
export const PANEL = 0.45; // the words always sit on flat brand colour in the top 45%

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
export const spring = (frame: number, start: number, len = 10, damping = 12) =>
	interpolate(frame, [start, start + len], [0, 1], {...clamp, easing: Easing.spring({damping})});

// The opening line lands word by word, fast enough to be readable within the first second.
export const Words: React.FC<{text: string; start: number; size: number; color?: string}> = ({text, start, size, color = INK}) => {
	const frame = useCurrentFrame();
	return (
		<div style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: `0 ${size * 0.28}px`, padding: '0 70px'}}>
			{text.split(' ').map((w, i) => {
				const p = spring(frame, start + i * 1.5, 6, 10);
				return (
					<span
						key={i}
						style={{
							fontFamily: '"Arial Black", Arial, sans-serif', fontWeight: 900, fontSize: size, lineHeight: 1.08,
							color, opacity: p, letterSpacing: '-0.02em',
							translate: `0px ${(1 - p) * 40}px`, scale: String(0.7 + 0.3 * p),
						}}
					>
						{w}
					</span>
				);
			})}
		</div>
	);
};

// Hook for the first 1.2 seconds, then the body line, always on flat brand colour.
export const Panel: React.FC<{hook: string; body: string; punch?: (i: number) => number}> = ({hook, body}) => {
	const frame = useCurrentFrame();
	const {fps, height} = useVideoConfig();
	const cut = Math.round(1.2 * fps);
	return (
		<div style={{position: 'absolute', top: 0, left: 0, right: 0, height: height * PANEL, background: Y,
			display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
			{frame < cut ? <Words text={hook} start={0} size={112} /> : <Words text={body} start={cut} size={92} />}
		</div>
	);
};

export const Bubbles: React.FC<{seed: string; n: number; top: number; bottom: number; color?: string; speed?: number}> = ({seed, n, top, bottom, color = 'rgba(255,255,255,0.85)', speed = 1}) => {
	const frame = useCurrentFrame();
	const {width} = useVideoConfig();
	return (
		<>
			{Array.from({length: n}).map((_, i) => {
				const x = random(`${seed}x${i}`) * width;
				const r = 6 + random(`${seed}r${i}`) * 18;
				const ph = random(`${seed}p${i}`);
				const p = (ph + (frame / 120) * (0.4 + random(`${seed}v${i}`) * 0.6) * speed) % 1;
				const y = bottom - p * (bottom - top);
				return (
					<div key={i} style={{position: 'absolute', left: x + Math.sin(frame / 12 + i) * 10, top: y,
						width: r * 2, height: r * 2, borderRadius: '50%', border: `3px solid ${color}`,
						opacity: Math.min(1, p * 6) * (1 - p)}} />
				);
			})}
		</>
	);
};

export const Can: React.FC<{width: number; style?: React.CSSProperties}> = ({width, style}) => (
	<Img src={staticFile('can.png')} style={{width, filter: 'drop-shadow(0 0 6px white) drop-shadow(0 26px 30px rgba(0,0,0,0.35))', ...style}} />
);

// The end card: the logo at 1.25x its file size (what Liftoff's logo check expects in a 1080 frame), then the line.
export const EndCard: React.FC<{line: string; start: number}> = ({line, start}) => {
	const frame = useCurrentFrame();
	const pop = spring(frame, start, 8, 9);
	return (
		<AbsoluteFill style={{background: Y, alignItems: 'center'}}>
			<Bubbles seed="end" n={40} top={500} bottom={1920} color="rgba(236,0,140,0.35)" />
			<Img src={staticFile('logo.png')} style={{position: 'absolute', top: 640, width: 384, height: 188, scale: String(0.8 + 0.2 * pop)}} />
			<div style={{position: 'absolute', top: 900, width: '100%'}}>
				<Words text={line} start={start + 6} size={84} />
			</div>
		</AbsoluteFill>
	);
};
