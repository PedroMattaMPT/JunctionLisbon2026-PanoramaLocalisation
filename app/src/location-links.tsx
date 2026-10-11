import React from 'react';
import { useT } from '@ds/rt';

export const googleMapsUrl = ({ lat, lng }: { lat: number; lng: number }) =>
  `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${lat},${lng}`)}`;

/** These links always use the estimate, never a nearby street camera's position. */
export function LocationLinks({ point, osm = false }: { point: { lat: number; lng: number }; osm?: boolean }) {
  const type = useT();
  const coordinate = encodeURIComponent(`${point.lat},${point.lng}`);
  return <div className="location-links" role="group" aria-label="Open estimated location">
    <a className={`aq-btn aq-btn-secondary ${type.label}`} href={googleMapsUrl(point)} target="_blank" rel="noopener noreferrer">Open Google Maps ↗</a>
    <a className={`aq-btn aq-btn-quiet ${type.label}`} href={`https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${coordinate}`} target="_blank" rel="noopener noreferrer">Open Google Street View ↗</a>
    {osm && <a className={`aq-btn aq-btn-quiet ${type.label}`} href={`https://www.openstreetmap.org/?mlat=${point.lat}&mlon=${point.lng}#map=18/${point.lat}/${point.lng}`} target="_blank" rel="noopener noreferrer">Open OSM ↗</a>}
  </div>;
}
