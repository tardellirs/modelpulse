export const Logo = ({ size = 32 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
    <rect x="1.5" y="1.5" width="29" height="29" rx="8" fill="#FFD21E" stroke="#1B1B1F" stroke-width="3" />
    <path d="M5.5 17h4.5l3-8 5 15 3-7h5.5" fill="none" stroke="#1B1B1F" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
);

// the sister project's mark, for the link to Paper Pulse
export const PaperPulseLogo = ({ size = 18, fill = "#FF8A6B" }: { size?: number; fill?: string }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
    <path d="M3 4.5A3 3 0 0 1 6 1.5h14.5l8.5 8.5v15.5a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3z" fill={fill} stroke="#1B1B1F" stroke-width="3" stroke-linejoin="round" />
    <path d="M20.5 1.5V7a3 3 0 0 0 3 3H29" fill="none" stroke="#1B1B1F" stroke-width="3" stroke-linejoin="round" />
    <path d="M6.5 19h4l2.5-6.5 4 11 2.5-6h5" fill="none" stroke="#1B1B1F" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
);
