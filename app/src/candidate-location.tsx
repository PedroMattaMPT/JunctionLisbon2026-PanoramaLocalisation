import React from 'react';
import { useT } from '@ds/rt';
import { point, type Candidate } from './model';
import { coordinates } from './format';
import { googleMapsUrl } from './location-links';

export function CandidateLocation({ candidate }: { candidate: Candidate }) {
  const location = point(candidate), type = useT();
  return <div className="candidate-location" role="group" aria-label="Candidate coordinates">
    {location ? <><span className={`${type.micro} aq-ink3`}>Lat, lng</span><span className={`candidate-location-value ${type.dataSm}`}>{coordinates(location.lat, location.lng)}</span><a className={`${type.micro} candidate-location-map`} href={googleMapsUrl(location)} target="_blank" rel="noopener noreferrer" aria-label={`Open candidate ${candidate.rank} in Google Maps`}>Google Maps ↗</a></> : <span className={`${type.micro} aq-ink3`}>Coordinates unavailable</span>}
  </div>;
}
