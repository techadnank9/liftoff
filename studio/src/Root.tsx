import React from 'react';
import {Composition} from 'remotion';
import {Beat} from './Beat';
import {DEMO_SECONDS, Demo} from './Demo';
import {Process} from './Process';
import {Secret} from './Secret';

// poppi's three directions, as Liftoff's Director wrote them (library/drinkpoppi-com/run.json).
// Each ends on the logo for longer than the 3-second check needs.
const FPS = 30;
export const RemotionRoot: React.FC = () => (
	<>
		<Composition id="PoppiProcess" component={Process} durationInFrames={10 * FPS} fps={FPS} width={1080} height={1920}
			defaultProps={{hook: 'Ever seen soda born?', body: 'Watch the bubbles go wild', endLine: 'poppi, made playful', endAt: Math.round(6.4 * FPS)}} />
		<Composition id="PoppiSecret" component={Secret} durationInFrames={8 * FPS} fps={FPS} width={1080} height={1920}
			defaultProps={{hook: 'My soda has a secret.', body: "It's not boring, promise.", endLine: 'poppi, obviously', endAt: Math.round(4.4 * FPS)}} />
		<Composition id="PoppiBeat" component={Beat} durationInFrames={12 * FPS} fps={FPS} width={1080} height={1920}
			defaultProps={{hook: 'Pop. Fizz. Repeat.', body: 'The can that steals focus', endLine: 'poppi in slow-mo', endAt: Math.round(7.6 * FPS)}} />
		<Composition id="LiftoffDemo" component={Demo} durationInFrames={DEMO_SECONDS * FPS} fps={FPS} width={1920} height={1080} />
	</>
);
