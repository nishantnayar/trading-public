export function EquityCurve() {
  return (
    <svg width="100%" viewBox="0 0 820 320" className="mt-3.5 block">
      <defs>
        <linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#2dd4bf" stopOpacity="0.28" />
          <stop offset="1" stopColor="#2dd4bf" stopOpacity="0" />
        </linearGradient>
      </defs>
      <line x1="55" y1="30" x2="55" y2="270" stroke="#1e2831" />
      <line x1="55" y1="270" x2="800" y2="270" stroke="#1e2831" />
      <line x1="55" y1="210" x2="800" y2="210" stroke="#161f27" />
      <line x1="55" y1="150" x2="800" y2="150" stroke="#161f27" />
      <line x1="55" y1="90" x2="800" y2="90" stroke="#161f27" />
      <text x="46" y="274" textAnchor="end" fill="#5f6b78" fontSize="11" fontFamily="IBM Plex Mono">
        $1.0M
      </text>
      <text x="46" y="214" textAnchor="end" fill="#5f6b78" fontSize="11" fontFamily="IBM Plex Mono">
        $1.1M
      </text>
      <text x="46" y="154" textAnchor="end" fill="#5f6b78" fontSize="11" fontFamily="IBM Plex Mono">
        $1.2M
      </text>
      <text x="46" y="94" textAnchor="end" fill="#5f6b78" fontSize="11" fontFamily="IBM Plex Mono">
        $1.3M
      </text>
      <path
        d="M55 255 L120 250 L185 240 L250 258 L315 230 L380 215 L445 205 L510 220 L575 185 L640 165 L705 150 L800 118"
        fill="none"
        stroke="#5f6b78"
        strokeWidth="1.6"
        strokeDasharray="4 4"
      />
      <path
        d="M55 258 L120 244 L185 220 L250 235 L315 195 L380 170 L445 178 L510 150 L575 128 L640 132 L705 96 L800 70 L800 270 L55 270 Z"
        fill="url(#eq)"
      />
      <path
        d="M55 258 L120 244 L185 220 L250 235 L315 195 L380 170 L445 178 L510 150 L575 128 L640 132 L705 96 L800 70"
        fill="none"
        stroke="#2dd4bf"
        strokeWidth="2.4"
      />
      <text x="55" y="290" fill="#5f6b78" fontSize="11" fontFamily="IBM Plex Mono">
        {"Sep'25"}
      </text>
      <text x="410" y="290" textAnchor="middle" fill="#5f6b78" fontSize="11" fontFamily="IBM Plex Mono">
        {"Mar'26"}
      </text>
      <text x="800" y="290" textAnchor="end" fill="#5f6b78" fontSize="11" fontFamily="IBM Plex Mono">
        {"Sep'26"}
      </text>
    </svg>
  );
}

export function ScoreHistogram() {
  return (
    <svg width="100%" viewBox="0 0 1120 90" className="block">
      <g fill="#233240">
        <rect x="10" y="60" width="26" height="20" />
        <rect x="40" y="52" width="26" height="28" />
        <rect x="70" y="40" width="26" height="40" />
        <rect x="100" y="28" width="26" height="52" />
        <rect x="130" y="20" width="26" height="60" />
        <rect x="160" y="14" width="26" height="66" />
        <rect x="190" y="12" width="26" height="68" />
        <rect x="220" y="16" width="26" height="64" />
      </g>
      <g fill="#f43f5e" opacity="0.8">
        <rect x="10" y="60" width="26" height="20" />
        <rect x="40" y="52" width="26" height="28" />
        <rect x="70" y="40" width="26" height="40" />
      </g>
      <g fill="#2b3a48">
        <rect x="250" y="10" width="26" height="70" />
        <rect x="280" y="9" width="26" height="71" />
        <rect x="310" y="10" width="26" height="70" />
        <rect x="340" y="12" width="26" height="68" />
        <rect x="370" y="16" width="26" height="64" />
        <rect x="400" y="14" width="26" height="66" />
        <rect x="430" y="12" width="26" height="68" />
        <rect x="460" y="10" width="26" height="70" />
        <rect x="490" y="9" width="26" height="71" />
        <rect x="520" y="9" width="26" height="71" />
        <rect x="550" y="10" width="26" height="70" />
        <rect x="580" y="12" width="26" height="68" />
        <rect x="610" y="14" width="26" height="66" />
        <rect x="640" y="16" width="26" height="64" />
        <rect x="670" y="18" width="26" height="62" />
        <rect x="700" y="16" width="26" height="64" />
        <rect x="730" y="14" width="26" height="66" />
        <rect x="760" y="14" width="26" height="66" />
        <rect x="790" y="16" width="26" height="64" />
        <rect x="820" y="20" width="26" height="60" />
        <rect x="850" y="24" width="26" height="56" />
        <rect x="880" y="30" width="26" height="50" />
      </g>
      <g fill="#22c55e" opacity="0.85">
        <rect x="910" y="36" width="26" height="44" />
        <rect x="940" y="42" width="26" height="38" />
        <rect x="970" y="48" width="26" height="32" />
        <rect x="1000" y="54" width="26" height="26" />
        <rect x="1030" y="60" width="26" height="20" />
        <rect x="1060" y="66" width="26" height="14" />
        <rect x="1090" y="70" width="20" height="10" />
      </g>
      <line x1="246" y1="4" x2="246" y2="84" stroke="#f43f5e" strokeWidth="1.5" strokeDasharray="3 3" />
      <line x1="906" y1="4" x2="906" y2="84" stroke="#22c55e" strokeWidth="1.5" strokeDasharray="3 3" />
    </svg>
  );
}

export function RankIcBars() {
  return (
    <svg width="100%" viewBox="0 0 520 300" className="mt-3.5 block">
      <line x1="40" y1="150" x2="500" y2="150" stroke="#2b3a48" />
      <text x="34" y="60" textAnchor="end" fill="#5f6b78" fontSize="10" fontFamily="IBM Plex Mono">
        .10
      </text>
      <text x="34" y="154" textAnchor="end" fill="#5f6b78" fontSize="10" fontFamily="IBM Plex Mono">
        0
      </text>
      <text x="34" y="244" textAnchor="end" fill="#5f6b78" fontSize="10" fontFamily="IBM Plex Mono">
        -.10
      </text>
      <g>
        <rect x="48" y="110" width="26" height="40" fill="#22c55e" />
        <rect x="82" y="96" width="26" height="54" fill="#22c55e" />
        <rect x="116" y="150" width="26" height="22" fill="#f43f5e" />
        <rect x="150" y="120" width="26" height="30" fill="#22c55e" />
        <rect x="184" y="88" width="26" height="62" fill="#22c55e" />
        <rect x="218" y="104" width="26" height="46" fill="#22c55e" />
        <rect x="252" y="150" width="26" height="14" fill="#f43f5e" />
        <rect x="286" y="126" width="26" height="24" fill="#22c55e" />
        <rect x="320" y="100" width="26" height="50" fill="#22c55e" />
        <rect x="354" y="118" width="26" height="32" fill="#22c55e" />
        <rect x="388" y="92" width="26" height="58" fill="#22c55e" />
        <rect x="422" y="112" width="26" height="38" fill="#22c55e" />
        <rect x="456" y="150" width="26" height="18" fill="#f43f5e" />
      </g>
      <text x="48" y="285" fill="#5f6b78" fontSize="10" fontFamily="IBM Plex Mono">
        {"Sep'25"}
      </text>
      <text x="482" y="285" textAnchor="end" fill="#5f6b78" fontSize="10" fontFamily="IBM Plex Mono">
        {"Sep'26"}
      </text>
    </svg>
  );
}

export function CvFolds() {
  return (
    <svg width="100%" viewBox="0 0 720 200" className="mt-2.5 block">
      <g fontFamily="IBM Plex Mono" fontSize="11">
        <text x="0" y="30" fill="#5f6b78">
          Fold 1
        </text>
        <rect x="60" y="20" width="240" height="14" fill="#233240" />
        <rect x="300" y="20" width="18" height="14" fill="#3a2a10" />
        <rect x="318" y="20" width="80" height="14" fill="#2dd4bf" />
        <text x="0" y="58" fill="#5f6b78">
          Fold 2
        </text>
        <rect x="60" y="48" width="340" height="14" fill="#233240" />
        <rect x="400" y="48" width="18" height="14" fill="#3a2a10" />
        <rect x="418" y="48" width="80" height="14" fill="#2dd4bf" />
        <text x="0" y="86" fill="#5f6b78">
          Fold 3
        </text>
        <rect x="60" y="76" width="440" height="14" fill="#233240" />
        <rect x="500" y="76" width="18" height="14" fill="#3a2a10" />
        <rect x="518" y="76" width="80" height="14" fill="#2dd4bf" />
        <text x="0" y="114" fill="#5f6b78">
          Fold 4
        </text>
        <rect x="60" y="104" width="540" height="14" fill="#233240" />
        <rect x="600" y="104" width="18" height="14" fill="#3a2a10" />
        <rect x="618" y="104" width="80" height="14" fill="#2dd4bf" />
        <text x="0" y="160" fill="#8b97a3">
          Legend
        </text>
      </g>
      <rect x="60" y="150" width="14" height="14" fill="#233240" />
      <text x="80" y="161" fill="#8b97a3" fontSize="11" fontFamily="IBM Plex Sans">
        Train
      </text>
      <rect x="150" y="150" width="14" height="14" fill="#3a2a10" />
      <text x="170" y="161" fill="#8b97a3" fontSize="11" fontFamily="IBM Plex Sans">
        Embargo (purged)
      </text>
      <rect x="320" y="150" width="14" height="14" fill="#2dd4bf" />
      <text x="340" y="161" fill="#8b97a3" fontSize="11" fontFamily="IBM Plex Sans">
        Validation
      </text>
    </svg>
  );
}

export function IcDecay() {
  return (
    <svg width="100%" viewBox="0 0 520 260" className="mt-3 block">
      <line x1="40" y1="30" x2="40" y2="210" stroke="#1e2831" />
      <line x1="40" y1="210" x2="500" y2="210" stroke="#1e2831" />
      <line x1="40" y1="90" x2="500" y2="90" stroke="#161f27" />
      <line x1="40" y1="150" x2="500" y2="150" stroke="#161f27" />
      <text x="32" y="94" textAnchor="end" fill="#5f6b78" fontSize="10" fontFamily="IBM Plex Mono">
        .08
      </text>
      <text x="32" y="154" textAnchor="end" fill="#5f6b78" fontSize="10" fontFamily="IBM Plex Mono">
        .04
      </text>
      <path
        d="M40 84 L110 88 L180 82 L250 90 L320 86 L390 92 L460 88 L500 90"
        fill="none"
        stroke="#5f6b78"
        strokeWidth="1.6"
        strokeDasharray="4 4"
      />
      <path
        d="M40 90 L110 96 L180 100 L250 108 L320 120 L390 128 L460 140 L500 148"
        fill="none"
        stroke="#2dd4bf"
        strokeWidth="2.4"
      />
      <text x="40" y="228" fill="#5f6b78" fontSize="10" fontFamily="IBM Plex Mono">
        deploy
      </text>
      <text x="500" y="228" textAnchor="end" fill="#5f6b78" fontSize="10" fontFamily="IBM Plex Mono">
        now
      </text>
    </svg>
  );
}
