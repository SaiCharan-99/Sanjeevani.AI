import { HashRouter, Link, Route, Routes, useLocation } from "react-router-dom";

import Screen1Camp from "./screens/Screen1Camp";
import Screen2Intake from "./screens/Screen2Intake";
import Screen3ScanIntro from "./screens/Screen3ScanIntro";
import Screen4LiveScan from "./screens/Screen4LiveScan";
import Screen4bLowLight from "./screens/Screen4bLowLight";
import Screen5Results from "./screens/Screen5Results";
import Screen5bLowSignal from "./screens/Screen5bLowSignal";
import Screen6Voice from "./screens/Screen6Voice";
import Screen7Analysing from "./screens/Screen7Analysing";
import Screen8WhatWeHeard from "./screens/Screen8WhatWeHeard";
import Screen9EditSymptoms from "./screens/Screen9EditSymptoms";
import Screen10NextStep from "./screens/Screen10NextStep";
import Screen11MotionCapture from "./screens/Screen11MotionCapture";
import Screen12Findings from "./screens/Screen12Findings";
import Screen13Assessment from "./screens/Screen13Assessment";
import Screen14Saved from "./screens/Screen14Saved";
import Screen15Profile from "./screens/Screen15Profile";
import Screen16Graph from "./screens/Screen16Graph";
import Screen17Village from "./screens/Screen17Village";

const SCREENS: { path: string; label: string; el: JSX.Element }[] = [
  { path: "/1", label: "1 Camp", el: <Screen1Camp /> },
  { path: "/2", label: "2 Intake", el: <Screen2Intake /> },
  { path: "/3", label: "3 Scan intro", el: <Screen3ScanIntro /> },
  { path: "/4", label: "4 Live scan", el: <Screen4LiveScan /> },
  { path: "/4b", label: "4b Low light", el: <Screen4bLowLight /> },
  { path: "/5", label: "5 Results", el: <Screen5Results /> },
  { path: "/5b", label: "5b Low signal", el: <Screen5bLowSignal /> },
  { path: "/6", label: "6 Voice", el: <Screen6Voice /> },
  { path: "/7", label: "7 Analysing", el: <Screen7Analysing /> },
  { path: "/8", label: "8 Heard", el: <Screen8WhatWeHeard /> },
  { path: "/9", label: "9 Edit symptoms", el: <Screen9EditSymptoms /> },
  { path: "/10", label: "10 Next step", el: <Screen10NextStep /> },
  { path: "/11", label: "11 Motion capture", el: <Screen11MotionCapture /> },
  { path: "/12", label: "12 Findings", el: <Screen12Findings /> },
  { path: "/13", label: "13 Assessment", el: <Screen13Assessment /> },
  { path: "/14", label: "14 Saved", el: <Screen14Saved /> },
  { path: "/15", label: "15 Profile", el: <Screen15Profile /> },
  { path: "/16", label: "16 Graph", el: <Screen16Graph /> },
  { path: "/17", label: "17 Village", el: <Screen17Village /> },
];

function Rail() {
  const location = useLocation();
  return (
    <div className="sticky top-0 z-50 bg-bg/95 backdrop-blur border-b border-line-soft">
      <div className="flex items-center gap-2.5 px-4 pt-3.5 pb-2.5">
        <div className="w-8 h-8 rounded-[10px] bg-accent text-accent-ink flex items-center justify-center flex-shrink-0 font-bold">
          S
        </div>
        <div>
          <h1 className="text-[17px] font-bold tracking-tight leading-tight">Sanjeevani</h1>
          <p className="text-xs text-text-3">Rural diagnostic · guided flow</p>
        </div>
      </div>
      <div className="flex gap-2 overflow-x-auto px-4 pb-3">
        {SCREENS.map((s) => (
          <Link
            key={s.path}
            to={s.path}
            className={`flex-none h-8 px-3.5 rounded-full border font-semibold text-[13px] whitespace-nowrap ${
              location.pathname === s.path
                ? "bg-accent border-accent text-accent-ink"
                : "bg-bg-2 border-line text-text-2"
            }`}
          >
            {s.label}
          </Link>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <HashRouter>
      <Rail />
      <div className="max-w-[560px] mx-auto px-4 pt-5 pb-10">
        <Routes>
          <Route path="/" element={SCREENS[0].el} />
          {SCREENS.map((s) => (
            <Route key={s.path} path={s.path} element={s.el} />
          ))}
        </Routes>
      </div>
    </HashRouter>
  );
}
