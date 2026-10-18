import React from 'react';
import {AbsoluteFill, Easing, Img, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {loadFont} from '@remotion/google-fonts/InterTight';
import {loadFont as loadMono} from '@remotion/google-fonts/JetBrainsMono';

// The Liftoff walkthrough: what it is, one launch from URL to proven videos, and how it learns.
const {fontFamily} = loadFont('normal', {weights: ['400', '500', '600', '700'], subsets: ['latin']});
const {fontFamily: mono} = loadMono('normal', {weights: ['400', '500'], subsets: ['latin']});

const BG = '#0A0A0B', PANEL = '#131315', INK = '#F2F1EE', SOFT = '#A3A19B', DIM = '#66645F';
const FLAME = '#F2853A', GO = '#5BD08A', HOLD = '#F2C063';
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const ease = Easing.bezier(0.2, 0.8, 0.2, 1);

const s = (t: number) => Math.round(t * 30);
const rise = (frame: number, at: number, len = 14) => interpolate(frame, [at, at + len], [0, 1], {...clamp, easing: ease});

// fade a whole scene in and out so cuts never jump
const Scene: React.FC<{len: number; children: React.ReactNode; bg?: string}> = ({len, children, bg = BG}) => {
	const f = useCurrentFrame();
	const o = interpolate(f, [0, 10, len - 10, len], [0, 1, 1, 0], clamp);
	return <AbsoluteFill style={{background: bg, opacity: o, fontFamily, color: INK}}>{children}</AbsoluteFill>;
};

const Label: React.FC<{children: React.ReactNode; at?: number; color?: string}> = ({children, at = 0, color = FLAME}) => {
	const f = useCurrentFrame();
	const p = rise(f, at);
	return <div style={{fontFamily: mono, fontSize: 24, letterSpacing: '0.04em', color, opacity: p, translate: `0px ${(1 - p) * 12}px`}}>{children}</div>;
};

const Head: React.FC<{children: React.ReactNode; at?: number; size?: number; style?: React.CSSProperties}> = ({children, at = 4, size = 84, style}) => {
	const f = useCurrentFrame();
	const p = rise(f, at, 18);
	return (
		<div style={{fontSize: size, fontWeight: 600, letterSpacing: '-0.035em', lineHeight: 1.04, opacity: p,
			translate: `0px ${(1 - p) * 30}px`, ...style}}>{children}</div>
	);
};

const Body: React.FC<{children: React.ReactNode; at?: number; style?: React.CSSProperties}> = ({children, at = 12, style}) => {
	const f = useCurrentFrame();
	const p = rise(f, at, 18);
	return <div style={{fontSize: 34, color: SOFT, lineHeight: 1.4, opacity: p, translate: `0px ${(1 - p) * 20}px`, ...style}}>{children}</div>;
};

// A screenshot in a browser frame that slowly drifts, so a still image reads as a live screen.
const Screen: React.FC<{src: string; at?: number; from?: number; to?: number; zoom?: [number, number]; w?: number; h?: number}> = ({src, at = 0, from = 0, to = 0, zoom = [1, 1.04], w = 1240, h = 698}) => {
	const f = useCurrentFrame();
	const {durationInFrames} = useVideoConfig();
	const p = rise(f, at, 20);
	const t = interpolate(f, [at, durationInFrames], [0, 1], {...clamp, easing: Easing.inOut(Easing.quad)});
	return (
		<div style={{width: w, height: h, borderRadius: 18, overflow: 'hidden', background: PANEL, opacity: p,
			border: '1px solid rgba(255,255,255,.14)', boxShadow: '0 40px 120px rgba(0,0,0,.6)', translate: `0px ${(1 - p) * 40}px`}}>
			<div style={{height: 38, background: '#1A1A1D', display: 'flex', alignItems: 'center', gap: 9, padding: '0 16px'}}>
				{['#ff5f57', '#febc2e', '#28c840'].map((c) => <div key={c} style={{width: 12, height: 12, borderRadius: 6, background: c}} />)}
			</div>
			<div style={{height: h - 38, overflow: 'hidden'}}>
				<Img src={staticFile(src)} style={{width: '100%', display: 'block', transformOrigin: '50% 0%',
					scale: String(interpolate(t, [0, 1], zoom)), translate: `0px ${-interpolate(t, [0, 1], [from, to])}px`}} />
			</div>
		</div>
	);
};

const Split: React.FC<{left: React.ReactNode; right: React.ReactNode}> = ({left, right}) => (
	<AbsoluteFill style={{flexDirection: 'row', alignItems: 'center', padding: '0 90px', gap: 70}}>
		<div style={{width: 470, display: 'flex', flexDirection: 'column', gap: 22}}>{left}</div>
		<div style={{flex: 1, display: 'flex', justifyContent: 'center'}}>{right}</div>
	</AbsoluteFill>
);

// 1. Title
const Title: React.FC = () => {
	const f = useCurrentFrame();
	const glow = interpolate(f, [0, 60], [0, 1], clamp);
	const lift = interpolate(f, [70, 140], [0, -60], {...clamp, easing: Easing.in(Easing.cubic)});
	return (
		<Scene len={s(5)}>
			<AbsoluteFill style={{background: `radial-gradient(ellipse at 50% 110%, rgba(242,133,58,${0.35 * glow}) 0%, transparent 60%)`}} />
			<AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', gap: 26, translate: `0px ${lift}px`}}>
				<div style={{fontSize: 90, opacity: rise(f, 0), translate: `0px ${-lift * 3}px`}}>🚀</div>
				<Head at={6} size={150} style={{textAlign: 'center'}}>Liftoff</Head>
				<Body at={18} style={{fontSize: 42, textAlign: 'center'}}>Launch videos, proven before they go out.</Body>
			</AbsoluteFill>
		</Scene>
	);
};

// 2. The problem
const Problem: React.FC = () => {
	const f = useCurrentFrame();
	const misses = [['Logo on screen', '2.0s', 'needs 3.0s'], ['Text contrast', '3.8', 'needs 4.5'], ['Brand colours', 'off', 'needs on brand']];
	return (
		<Scene len={s(7)}>
			<Split
				left={<>
					<Label>the problem</Label>
					<Head>AI makes launch videos fast.</Head>
					<Head at={24} style={{color: SOFT}}>Nobody checks them.</Head>
				</>}
				right={
					<div style={{display: 'flex', flexDirection: 'column', gap: 22, width: 760}}>
						{misses.map(([what, got, need], i) => {
							const p = rise(f, s(1.6) + i * 12);
							return (
								<div key={what} style={{display: 'flex', alignItems: 'center', gap: 26, padding: '30px 36px', borderRadius: 18,
									background: PANEL, border: '1px solid rgba(255,255,255,.08)', opacity: p, translate: `${(1 - p) * 60}px 0px`}}>
									<div style={{width: 18, height: 18, borderRadius: 9, background: HOLD}} />
									<div style={{fontSize: 38, flex: 1}}>{what}</div>
									<div style={{fontFamily: mono, fontSize: 34, color: HOLD}}>{got}</div>
									<div style={{fontFamily: mono, fontSize: 24, color: DIM, width: 220, textAlign: 'right'}}>{need}</div>
								</div>
							);
						})}
					</div>
				}
			/>
		</Scene>
	);
};

// 3. Paste a URL: the real landing page, zooming in on its input while the URL types itself
const Paste: React.FC = () => {
	const f = useCurrentFrame();
	const typed = 'drinkpoppi.com'.slice(0, Math.max(0, Math.floor((f - s(1.6)) / 2.2)));
	const k = 1240 / 1920; // screenshot scale inside the frame
	const ix = (687 + 12) * k, iy = 480.5 * k, ih = 46 * k;
	const z = interpolate(f, [s(0.6), s(2.0)], [1, 1.7], {...clamp, easing: ease});
	const p = rise(f, 0, 20);
	return (
		<Scene len={s(7)}>
			<Split
				left={<>
					<Label>step 1</Label>
					<Head>Paste a brand's website.</Head>
					<Body>Liftoff reads it for the name, colours, logo and tone. No brief to fill in.</Body>
				</>}
				right={
					<div style={{width: 1240, height: 698, borderRadius: 18, overflow: 'hidden', background: PANEL, opacity: p,
						border: '1px solid rgba(255,255,255,.14)', boxShadow: '0 40px 120px rgba(0,0,0,.6)'}}>
						<div style={{height: 38, background: '#1A1A1D', display: 'flex', alignItems: 'center', gap: 9, padding: '0 16px'}}>
							{['#ff5f57', '#febc2e', '#28c840'].map((c) => <div key={c} style={{width: 12, height: 12, borderRadius: 6, background: c}} />)}
						</div>
						<div style={{height: 660, overflow: 'hidden'}}>
							<div style={{position: 'relative', transformOrigin: `${ix + 120}px ${iy + ih / 2}px`, scale: String(z)}}>
								<Img src={staticFile('demo/landing.png')} style={{width: 1240, display: 'block'}} />
								<div style={{position: 'absolute', left: ix - 4, top: iy + 3, height: ih - 6, width: 220, background: '#141416',
									display: 'flex', alignItems: 'center', paddingLeft: 4, fontSize: 17 * k, color: INK, opacity: f > s(1.5) ? 1 : 0}}>
									{typed}<span style={{opacity: Math.floor(f / 8) % 2 ? 1 : 0, color: FLAME}}>|</span>
								</div>
							</div>
						</div>
					</div>
				}
			/>
		</Scene>
	);
};

// 4. Research
const Research: React.FC = () => (
	<Scene len={s(7)}>
		<Split
			left={<>
				<Label>step 2</Label>
				<Head>It looks at what's working right now.</Head>
				<Body>Viral Shorts from the last 30 days in the brand's category, found live with You.com and YouTube.</Body>
			</>}
			right={<Screen src="demo/mc_top.png" from={60} to={150} zoom={[1.3, 1.4]} />}
		/>
	</Scene>
);

// 5. Done means done: the checklist is written before anything is made
const Checklist: React.FC = () => {
	const f = useCurrentFrame();
	const checks = ['6 to 15 seconds long', 'Vertical, 9:16', 'Logo on screen at least 3s', 'Colours stay on brand', 'Text contrast 4.5 or better',
		'A hook in the first second', 'Brand name on the last frame', 'No competitor logos', 'No calorie count', 'No health claims'];
	return (
		<Scene len={s(8)}>
			<Split
				left={<>
					<Label>step 3</Label>
					<Head>It writes down what done means, first.</Head>
					<Body>Ten checks, each a number it can measure or a yes or no question. Before a single frame exists.</Body>
				</>}
				right={
					<div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, width: 1000}}>
						{checks.map((c, i) => {
							const p = rise(f, s(1.2) + i * 5, 12);
							return (
								<div key={c} style={{display: 'flex', alignItems: 'center', gap: 18, padding: '24px 26px', borderRadius: 16, background: PANEL,
									border: '1px solid rgba(255,255,255,.08)', opacity: p, scale: String(0.94 + 0.06 * p), fontSize: 30}}>
									<div style={{fontFamily: mono, fontSize: 22, color: DIM, width: 34}}>{String(i + 1).padStart(2, '0')}</div>{c}
								</div>
							);
						})}
					</div>
				}
			/>
		</Scene>
	);
};

// 6. Checked by someone else
const Verify: React.FC = () => {
	const f = useCurrentFrame();
	const holdP = rise(f, s(1.0));
	const goP = rise(f, s(4.0));
	return (
		<Scene len={s(9)}>
			<Split
				left={<>
					<Label>step 4</Label>
					<Head>Then a separate checker measures every video.</Head>
					<Body>A different model family, and it never sees the maker's notes. A miss goes back with exactly what failed.</Body>
				</>}
				right={
					<div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 26}}>
						<div style={{borderRadius: 18, overflow: 'hidden', border: '1px solid rgba(255,255,255,.14)'}}>
							<OffthreadVideo src={staticFile('demo/hold-then-go.mp4')} muted style={{width: 900, display: 'block'}} />
						</div>
						<div style={{display: 'flex', gap: 22}}>
							<div style={{padding: '18px 26px', borderRadius: 14, background: 'rgba(242,192,99,.12)', color: HOLD, fontSize: 28, opacity: holdP}}>
								<b>Try 1: sent back.</b> Logo 2.0s, contrast 3.8
							</div>
							<div style={{padding: '18px 26px', borderRadius: 14, background: 'rgba(91,208,138,.12)', color: GO, fontSize: 28, opacity: goP}}>
								<b>Try 2: passed.</b> Logo 3.25s, contrast 13.3
							</div>
						</div>
					</div>
				}
			/>
		</Scene>
	);
};

// 7. The result: three poppi videos
const Result: React.FC = () => {
	const f = useCurrentFrame();
	const vids = [['A', 'Ever seen soda born?'], ['B', 'My soda has a secret.'], ['C', 'Pop. Fizz. Repeat.']];
	return (
		<Scene len={s(11)}>
			<AbsoluteFill style={{alignItems: 'center', paddingTop: 70, gap: 40}}>
				<div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14}}>
					<Label>for poppi</Label>
					<Head size={68} style={{textAlign: 'center'}}>3 of 3 ready to post. It didn't need me once.</Head>
				</div>
				<div style={{display: 'flex', gap: 46}}>
					{vids.map(([v, name], i) => {
						const p = rise(f, s(0.8) + i * 8, 18);
						return (
							<div key={v} style={{display: 'flex', flexDirection: 'column', gap: 16, opacity: p, translate: `0px ${(1 - p) * 60}px`}}>
								<div style={{width: 380, height: 676, borderRadius: 22, overflow: 'hidden', border: '1px solid rgba(255,255,255,.14)'}}>
									<OffthreadVideo src={staticFile(`demo/poppi_${v}.mp4`)} muted style={{width: '100%', height: '100%', objectFit: 'cover'}} />
								</div>
								<div style={{display: 'flex', justifyContent: 'space-between', fontSize: 26}}>
									<span>{name}</span><span style={{color: GO, fontFamily: mono, fontSize: 22}}>10/10</span>
								</div>
							</div>
						);
					})}
				</div>
			</AbsoluteFill>
		</Scene>
	);
};

// 8. It learns
const Learn: React.FC = () => {
	const f = useCurrentFrame();
	const n = Math.round(interpolate(f, [s(2.2), s(3.6)], [0, 50], {...clamp, easing: ease}));
	return (
		<Scene len={s(9)}>
			<Split
				left={<>
					<Label>and it learns</Label>
					<Head>Every miss becomes a rule. A rule stays only if it helps.</Head>
					<Body>Tested on launch briefs it has never seen.</Body>
					<div style={{display: 'flex', alignItems: 'baseline', gap: 24, marginTop: 10, opacity: rise(f, s(1.8))}}>
						<span style={{fontSize: 110, fontWeight: 600, color: DIM, letterSpacing: '-0.04em'}}>0%</span>
						<span style={{fontSize: 60, color: DIM}}>→</span>
						<span style={{fontSize: 110, fontWeight: 600, color: GO, letterSpacing: '-0.04em'}}>{n}%</span>
					</div>
					<Body at={s(2.4)} style={{fontSize: 26}}>of videos passed every check on the first try</Body>
				</>}
				right={<Screen src="demo/mc_learn_crop.png" from={0} to={0} zoom={[1, 1.04]} />}
			/>
		</Scene>
	);
};

// 9. End
const End: React.FC = () => {
	const f = useCurrentFrame();
	return (
		<Scene len={s(6)}>
			<AbsoluteFill style={{background: `radial-gradient(ellipse at 50% 110%, rgba(242,133,58,.3) 0%, transparent 60%)`}} />
			<AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', gap: 28}}>
				<Head size={130} style={{textAlign: 'center'}}>Done means done.</Head>
				<Body at={14} style={{fontSize: 40, textAlign: 'center', color: INK}}>github.com/techadnank9/liftoff</Body>
				<div style={{fontFamily: mono, fontSize: 24, color: DIM, opacity: rise(f, 26), marginTop: 30}}>
					Crusoe Managed Inference · NVIDIA Nemotron · DeepSeek · You.com · Remotion
				</div>
			</AbsoluteFill>
		</Scene>
	);
};

export const SCENES: [React.FC, number][] = [[Title, 5], [Problem, 7], [Paste, 7], [Research, 7], [Checklist, 8], [Verify, 9], [Result, 11], [Learn, 9], [End, 6]];
export const DEMO_SECONDS = SCENES.reduce((a, [, d]) => a + d, 0);

export const Demo: React.FC = () => {
	let at = 0;
	return (
		<AbsoluteFill style={{background: BG}}>
			{SCENES.map(([C, d], i) => {
				const from = s(at);
				at += d;
				return <Sequence key={i} from={from} durationInFrames={s(d)}><C /></Sequence>;
			})}
		</AbsoluteFill>
	);
};
