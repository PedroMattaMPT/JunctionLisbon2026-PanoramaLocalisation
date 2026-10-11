import React, { useEffect, useRef } from 'react';
import { Button } from '@ds/base';
import { Wordmark } from '@ds/shell';
import { MapView } from '@ds/map';

export function Welcome({ onStart }: { onStart(): void }) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, []);
  return <main className="welcome">
    <header className="welcome-header"><Wordmark size={36} /><span className="console-label aq-ink3">Panorama localisation</span></header>
    <div className="welcome-body">
      <section className="welcome-copy">
        <p className="welcome-eyebrow console-label">Look closer. Find the place.</p>
        <h1 ref={heading} tabIndex={-1}>Where could<br /><em>here</em> be?</h1>
        <p className="welcome-description">Every panorama leaves clues. Watch signs, streets and scenery come together, until a place comes into focus.</p>
        <Button variant="primary" icon="forward" onClick={onStart}>Start exploring</Button>
        <p className="console-micro aq-ink3">One panorama. Its visible clues. A best estimate.</p>
      </section>
      <div className="welcome-atlas" aria-hidden="true">
        <div className="welcome-atlas-map"><MapView width={640} height={520} view={{ lat: 43, lng: -3, span: 24 }} candidates={[]} refs={[]} rings={[]} zones={[]} labels={false} legend={false} offline={false} /></div>
        <svg className="welcome-atlas-marks" viewBox="0 0 640 520" fill="none">
          <circle cx="290" cy="315" r="138" /><circle cx="290" cy="315" r="90" /><circle cx="290" cy="315" r="38" />
          <path d="M290 147V189M290 441V483M122 315H164M416 315H458" />
          <path className="welcome-atlas-cross" d="M280 315H300M290 305V325" />
        </svg>
        <span className="welcome-atlas-north console-label">N ↑</span>
        <div className="welcome-atlas-caption"><span className="console-label">A closer look at the world</span><span className="console-micro aq-ink3">Portugal · Spain · France</span></div>
      </div>
    </div>
    <ol className="welcome-steps" aria-label="How it works">
      <li><span className="console-data-sm">01</span><div><h2 className="console-heading">Bring a panorama</h2><p className="console-body aq-ink2">Choose your 360° photograph.</p></div></li>
      <li><span className="console-data-sm">02</span><div><h2 className="console-heading">Follow the clues</h2><p className="console-body aq-ink2">See observations and their explanations arrive.</p></div></li>
      <li><span className="console-data-sm">03</span><div><h2 className="console-heading">Watch the map narrow</h2><p className="console-body aq-ink2">From the search area to a supported estimate.</p></div></li>
    </ol>
  </main>;
}
