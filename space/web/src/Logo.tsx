export const Logo = ({ size = 32 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
    <rect x="1.5" y="1.5" width="29" height="29" rx="8" fill="#FFD21E" stroke="#1B1B1F" stroke-width="3" />
    <path d="M5.5 17h4.5l3-8 5 15 3-7h5.5" fill="none" stroke="#1B1B1F" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
);
