export function BrandMark({ className = "wordmark__mark" }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      focusable="false"
      viewBox="0 0 64 64"
    >
      <rect fill="#5f9dff" height="64" width="64" />
      <circle
        cx="26.5"
        cy="26.5"
        fill="#f4f1e7"
        r="16"
        stroke="#071b2d"
        strokeWidth="3"
      />
      <path
        d="M38.5 38.5 53 53"
        fill="none"
        stroke="#071b2d"
        strokeLinecap="square"
        strokeWidth="6"
      />
      <path
        d="M19 18.5v16M19 19h14M19 26.5h11M19 34h14"
        fill="none"
        stroke="#071b2d"
        strokeLinecap="square"
        strokeWidth="3"
      />
      <circle cx="33" cy="19" fill="#5f9dff" r="2.25" />
    </svg>
  );
}
