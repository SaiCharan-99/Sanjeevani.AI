/** App mark: a pulse line inside a rounded leaf/shield, echoing the vitals
 * focus (rPPG waveform) and the "camp health" framing. Single accent colour
 * so it drops onto the dark theme without extra tokens. */
export function Logo({ size = 34 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 34 34"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className="flex-shrink-0"
    >
      <rect width="34" height="34" rx="9" fill="#84D3B8" />
      <path
        d="M6 18h4.2l2-4.6 3 9.6 2.6-13 2.4 8h5.8"
        stroke="#0B1714"
        strokeWidth="2.1"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}
