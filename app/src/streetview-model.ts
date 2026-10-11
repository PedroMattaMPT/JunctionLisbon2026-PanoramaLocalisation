export const wrap = (value: number) => (value % 360 + 360) % 360;
export const angleDelta = (to: number, from: number) => wrap(to - from + 180) - 180;
// Viewer uses image yaw: 0 at the left edge, 180 at the image centre.
// The provider's heading is the bearing at that centre; northOffset alone doesn't turn it.
export const streetYaw = (bearing: number, centreHeading: number) => wrap(bearing - centreHeading + 180);
export const streetBearing = (imageYaw: number, centreHeading: number) => wrap(imageYaw - 180 + centreHeading);
export const alignmentOffset = (originalYaw: number, streetImageYaw: number) => angleDelta(streetImageYaw, originalYaw);
export function distanceWarning(metres: number): string {
  if (metres > 1000) return 'No street panorama within 1 km.';
  return metres > 50 ? `The nearest picture is ${Math.round(metres)} m away. Compare the area, not the exact camera spot.` : '';
}
